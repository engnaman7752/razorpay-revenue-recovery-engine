# START HERE — get everything running, in order

Do these in order. Each step says what success looks like. If a step fails,
stop there and fix it before moving on.

Everything runs from `D:\Hackathon\razorpay-recovery`.

> **Prefer VS Code?** Open the repo folder and use
> **Ctrl+Shift+P → Tasks: Run Task → ▶ START EVERYTHING** — it launches all
> three services in their own terminal tabs, no venv activation needed.
> Details in `docs\vscode.md`. The steps below are the manual equivalent.

---


> **Which port is the backend on?** One place decides: `SERVER_PORT` in `.env`
> (this machine is set to **8081** because 8080 was taken). Spring binds to it,
> the dashboard's vite proxy reads it, and `scripts/setup_demo.py` calls it — so
> they can't drift apart. Change it in `.env` only, never in `application.yml`.
> When vite starts it prints `[vite] proxying /api -> http://localhost:8081`;
> if that line disagrees with your backend's `Tomcat started on port(s)` line,
> that is the bug.

## Step 0 · Create the database  (once, 10 seconds)

```powershell
psql -U postgres -c "CREATE DATABASE recovery;"
```

**Success:** `CREATE DATABASE`
(`already exists` is also fine — move on.)

Flyway creates the *tables* automatically. It does not create the database.

---

## Step 1 · Start the backend  (terminal 1)

In IntelliJ press Run on `RecoveryApplication`, or:

```powershell
cd backend
mvn package
java -jar target\recovery-backend-0.1.0.jar --server.port=8081
```

**Success:** `Started RecoveryApplication in X seconds` and
`Tomcat started on port 8080`. In the log you should see Flyway applying
`V1__init` and `V2__batch_result`.

**Check it:**
```powershell
curl http://localhost:8080/api/health
```
Expect `{"status":"ok","cases_in_db":0}`

> If you get `Unsupported class file major version` or byte-buddy errors:
> switch IntelliJ to **JDK 17 or 21** (File → Project Structure → SDK).
> You are currently on JDK 24, which Hibernate 6.5 does not officially know.

Leave this running.

---

## Step 2 · Start the agent  (terminal 2)

```powershell
cd D:\Hackathon\razorpay-recovery\agent
..\.venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

(The agent reads the repo-root `.env` by itself — no activation or
`load-env` needed.)

**Success:**
```powershell
curl http://localhost:8000/health
```
Expect `{"status":"ok","durable_checkpoints":true}`

`durable_checkpoints: true` is important — it means paused approvals will
survive a restart. If it says `false`, `.env` did not load in that terminal.

Leave this running.

---

## Step 3 · Fill the dashboard — run the batch  (terminal 3)

This is the step people forget. Until you run it, the dashboard is empty.
Needs steps 1 and 2 already running.

```powershell
cd D:\Hackathon\razorpay-recovery\backend
java -jar target\recovery-backend-0.1.0.jar --server.port=8081 `
  --recovery.batch.enabled=true --recovery.batch.include-agent=true `
  --server.port=9090
```

**Success:** takes 2–4 minutes, then prints four lines like
`RESULT strategy=AGENT recovered_paise=153696700 ...`
and writes `eval\results.md`.

Press Ctrl-C when it finishes.

---

## Step 4 · Start the dashboard  (terminal 4)

```powershell
cd D:\Hackathon\razorpay-recovery\frontend
npm install
npm run dev
```

Open **http://localhost:5173**

**Success:** the hero shows about **₹15,36,967 recovered of ₹23,53,507 at
risk**, charts are populated, and the Approvals tab has cases waiting.

You now have a complete working demo. Everything below is bonus credibility.

---

## Step 5 · Prove Razorpay is real  (2 minutes)

```powershell
cd D:\Hackathon\razorpay-recovery
python scripts\razorpay_smoke.py
```

**Success:** prints a real `https://rzp.io/...` link. Open it in a browser —
that is a genuine Razorpay checkout page, created by the same code the agent
calls in live mode.

**If you get 401:** your key pair is wrong. Regenerate in
Dashboard → Account & Settings → API Keys, in **Test Mode**, and update `.env`.

Do this today, not on demo day.

---

## Step 5.5 · Stage an approval — DO THIS BEFORE EVERY DEMO

The batch auto-approves high-value cases, so afterwards the **Approvals tab is
empty** — and the approval flow is your strongest demo moment. Put one case
back in the queue (needs backend AND agent running):

```powershell
cd D:\Hackathon\razorpay-recovery
.\.venv\Scripts\Activate.ps1
python scripts\setup_demo.py
```

**Success:** prints `READY — 1 case(s) waiting for approval` plus the two URLs
to open. Refresh the dashboard and the Approvals tab now has a case.

Re-run this any time you approve everything while rehearsing.

---

> Want to drive Razorpay by hand — curl calls, test UPI IDs, the full
> webhook loop? See **`docs\razorpay-manual.md`**.

## Step 6 · Rehearse the live proof  (5 minutes)

```powershell
cd agent
python ..\scripts\prove.py case      # one payment, both approaches, ~5 sec
python ..\scripts\prove.py batch     # all 300 computed live, ~45 sec
```

These are your answer to "anyone can claim 3.3×". Practise talking over them.

---

## Step 7 · OPTIONAL — full live webhook loop

Only if steps 0–6 all work and you have spare time. Needs a public URL:

1. `ngrok http 8080`
2. Razorpay Dashboard → Webhooks → add `https://<ngrok-url>/webhook/razorpay`
   with secret `whsec_8b64c1a9d91064227a92bb4d01f05373` (the one in `.env`)
   and events `payment.failed`, `payment_link.paid`, `order.paid`
3. Restart the backend with `GATEWAY_MODE=live` in `.env`
4. Fail a test payment → watch a LIVE case appear on the dashboard

Full detail in `docs\phase6-live-demo.md`.

---

## Daily restart (after the first time)

```powershell
# terminal 1
cd backend; java -jar target\recovery-backend-0.1.0.jar --server.port=8081
# terminal 2
.\.venv\Scripts\Activate.ps1; . .\scripts\load-env.ps1; cd agent; uvicorn main:app --port 8000
# terminal 3
cd frontend; npm run dev
```

The database keeps your batch results, so you only re-run the batch if you
want fresh data.

**Before presenting:** run `python scripts\setup_demo.py` so a case is waiting
in the Approvals tab. Without it that tab is empty.

---

## Which doc for what

| Need | File |
|---|---|
| What to say in the demo | `docs\demo-cheatsheet.md` |
| 5-minute video script | `docs\pitch-script.md` |
| How the simulation works | `docs\simulation.md` |
| Something broke | `docs\local-run.md` (troubleshooting table) |
| Deploy to the internet | `docs\deploy.md` |
