# Running and testing the whole project locally

Three ways in, fastest first. Do step 0 once for all of them.

## 0. One-time setup

```powershell
cd D:\Hackathon\razorpay-recovery
copy env.local.txt .env

# check you have Python 3.10+ (3.11 recommended)
python --version

# one virtual environment at the repo root, shared by the agent and the
# dev preview server
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # prompt becomes (.venv) ...
python -m pip install --upgrade pip
pip install -r agent\requirements.txt
```

If PowerShell refuses to run the activate script
(*"running scripts is disabled on this system"*), either allow it for this
window only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

or use plain `cmd.exe` instead:

```bat
.venv\Scripts\activate.bat
```

Verify the install:

```powershell
python -c "import langgraph, fastapi, httpx, yaml; print('agent deps OK')"
```

**Activate the venv in every new terminal** that runs Python — the prompt must
show `(.venv)`. `.venv\` is gitignored, and Docker (Option B) does not need it:
each container builds its own environment.

### Database: create it once

Flyway builds every **table** on first backend boot, but nothing creates the
**database** — do that once yourself:

```powershell
psql -U postgres -c "CREATE DATABASE recovery;"
# or:  psql -U postgres -f scripts\create-db.sql
```

Then point `.env` at your local Postgres (already done if you use the
`env.local.txt` I generated):

```
DATABASE_URL=jdbc:postgresql://localhost:5432/recovery
DATABASE_USER=postgres
DATABASE_PASSWORD=7752
```

The agent needs the same database in psycopg spelling; it derives that from
the JDBC URL plus user/password automatically, so one `.env` drives both.

To confirm the schema after the backend's first start:

```powershell
psql -U postgres -d recovery -c "\dt"
# expect: recovery_case, decision_log, ev_stats, scheduled_retry,
#         batch_result, flyway_schema_history (+ checkpoint tables from the agent)
```

### How `.env` reaches each service

| Service | How it gets `.env` |
|---|---|
| **backend** (`java -jar`, `mvn spring-boot:run`, IntelliJ) | automatic — `application.yml` imports the repo-root `.env` as a property source |
| **agent** (`uvicorn`) | not automatic — dot-source the loader first |
| **docker compose** | automatic |

So the backend needs nothing but the file existing at the repo root:

```powershell
copy env.local.txt .env      # if you have not already
```

Real OS environment variables still override the file, so Docker and CI are
unaffected. For the agent, load the variables into that terminal:

```powershell
. .\scripts\load-env.ps1
```

It prints what it loaded so you can see the database URL and whether the
Gemini key is present.

> **Already running Postgres on 5432?** Then `docker compose up` (Option B)
> will fail to bind that port. Either stop your local service for the demo, or
> use Option C and let the app talk to the Postgres you already have.

---

## Option A — UI only, no Java, ~2 minutes

Best for rehearsing the demo or checking the dashboard. Runs the **real
LangGraph agent** over 80 synthetic cases in memory; no database, no JVM.

```powershell
# terminal 1 — fake backend serving /api, driven by the real agent graph
cd D:\Hackathon\razorpay-recovery
.\.venv\Scripts\Activate.ps1
cd agent
python ..\frontend\dev-mock-api.py      # ~40s to seed, prints "seeded 80 cases"

# terminal 2 — dashboard
cd D:\Hackathon\razorpay-recovery\frontend
npm install
npm run dev                             # http://localhost:5173
```

Everything on screen is genuine: EV rankings, guard vetoes, and two cases
left paused in the approvals queue that really resume when you click Approve.

---

## Option B — full stack with Docker (the real thing)

Needs Docker Desktop running.

```powershell
cd D:\Hackathon\razorpay-recovery
docker compose up --build          # first build ~3-5 min (Maven + npm)
```

Check all three are alive:

```powershell
curl http://localhost:8080/api/health     # {"status":"ok","cases_in_db":0}
curl http://localhost:8000/health         # {"status":"ok","durable_checkpoints":true}
start http://localhost:5173               # dashboard (empty until you seed)
```

Seed the dashboard by running the 300-case batch (separate port so it does not
clash with the running web server):

```powershell
docker compose exec backend java -jar app.jar `
  --recovery.batch.enabled=true --recovery.batch.include-agent=true --server.port=9090
```

Takes ~1-3 minutes. Watch for `RESULT strategy=AGENT recovered_paise=...`, then
refresh the dashboard.

Human-in-the-loop demo (the one judges remember):

```powershell
# find a paused case
curl http://localhost:8080/api/escalations
# kill the agent mid-pause and bring it back — the checkpoint is in Postgres
docker compose restart agent
# approve from the dashboard's Approvals tab, or:
curl -X POST http://localhost:8080/api/escalations/<CASE_ID>/resolve `
  -H "Content-Type: application/json" -d '{\"approved\":true}'
```

Stop everything: `docker compose down` (add `-v` to wipe the database).

---

## Option C — services by hand (no Docker)

Needs JDK 17, Maven, Python 3.11, Node 20, and a local Postgres with a
`recovery` database owned by user `recovery` / password `recovery`.

```powershell
# 0 load secrets into this terminal (repeat in every terminal below)
. .\scripts\load-env.ps1

# 1 backend
cd backend
mvn package
java -jar target\recovery-backend-0.1.0.jar

# 2 agent   (new terminal: activate venv, then load env)
.\.venv\Scripts\Activate.ps1
. .\scripts\load-env.ps1
cd agent
$env:BACKEND_BASE_URL="http://localhost:8080"
uvicorn main:app --port 8000
# /health should report  "durable_checkpoints": true

# 3 frontend
cd frontend
npm install; npm run dev

# 4 batch, once the first two are up
cd backend
java -jar target\recovery-backend-0.1.0.jar --recovery.batch.enabled=true `
  --recovery.batch.include-agent=true --server.port=9090
```

---

## Tests

```powershell
# venv active
cd agent;   python -m pytest tests\ -v      # 45 tests
cd backend; mvn test                        # webhook HMAC verification
```

The human-in-the-loop tests need Postgres reachable at
`postgresql://recovery:recovery@localhost:5432/recovery`; they skip cleanly if
it is not.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Dashboard says "No batch results yet" | The batch has not run. Run the seed command above. |
| `/api/metrics` empty after batch | Batch ran without `--recovery.batch.include-agent=true`, so there is no AGENT row. |
| Agent 500s on every tool call | `AGENT_SHARED_SECRET` differs between backend and agent. Both read `.env`. |
| `durable_checkpoints: false` | The agent has no `DATABASE_URL`; pauses will not survive a restart. |
| `FATAL: database "recovery" does not exist` | Create it — Flyway makes tables, not the database. See above. |
| `password authentication failed for user "recovery"` | The literal name `recovery` means `.env` was not found — those are the built-in fallbacks. Check `.env` exists at the repo root (`copy env.local.txt .env`) and that your IDE's working directory is the repo root or `backend\`. |
| `password authentication failed` for your own user | `DATABASE_USER` / `DATABASE_PASSWORD` in `.env` don't match your Postgres. |
| `durable_checkpoints: false` after load-env | You started uvicorn in a terminal where `.env` was never loaded. |
| Backend exits at startup | Postgres not up yet, or a Flyway checksum mismatch after editing a migration — `docker compose down -v` and start again. |
| `ModuleNotFoundError: langgraph` | The venv is not active in that terminal — no `(.venv)` in the prompt. |
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again. |
| `pip` installs but `python` still misses them | Two Pythons on PATH. Use `python -m pip install ...` inside the venv. |
| Port already in use | Something else on 8080 / 8000 / 5173 / 5432. |
| Batch is slow | Normal: 300 cases × several HTTP round-trips each. |
