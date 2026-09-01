# Live deployment — Vercel (frontend) + Neon (Postgres) + Render (backend & agent)

Vercel has no Java runtime, so the Spring Boot backend and the always-on agent
run on Render (free tier); Vercel serves the dashboard; Neon holds the data.
Everything deploys from the GitHub repo — push the repo first.

## 0. Secrets you'll need (see README table)

| Var | Source |
|---|---|
| RAZORPAY_KEY_ID / KEY_SECRET | Razorpay Dashboard (Test Mode) → API Keys |
| RAZORPAY_WEBHOOK_SECRET | invent one; reuse when creating the webhook |
| GOOGLE_API_KEY | aistudio.google.com → Get API key (starts with AIza) |
| AGENT_SHARED_SECRET | invent one (e.g. `openssl rand -hex 24`); same on both services |
| Neon connection | neon.tech project → Connection Details |

## 1. Neon (database)

1. neon.tech → New Project (region close to you, e.g. aws ap-southeast-1).
2. From **Connection Details** take host, database, user, password.
3. You'll use it in TWO formats:
   - backend (JDBC): `jdbc:postgresql://<host>/<db>?sslmode=require`
     plus `DATABASE_USER` / `DATABASE_PASSWORD` separately.
   - agent (psycopg): the plain string Neon shows:
     `postgresql://<user>:<password>@<host>/<db>?sslmode=require`
4. Nothing to create manually — Flyway makes the schema on first backend boot,
   and the agent's PostgresSaver makes its checkpoint tables.

Tip: use the **pooled** connection string Neon offers for the backend (Hikari
pool + Neon's pooler is fine); the agent's single checkpoint connection can use
the direct (unpooled) host.

## 2. Render (backend + agent)

1. render.com → New → **Blueprint** → select the GitHub repo. `render.yaml`
   defines both services (Docker, free plan).
2. Fill the prompted env vars:
   - both: `AGENT_SHARED_SECRET` (same value!)
   - backend: Neon JDBC URL + user + password, Razorpay keys, webhook secret,
     `AGENT_BASE_URL=https://recovery-agent.onrender.com`,
     `FRONTEND_ORIGIN=https://<your-app>.vercel.app` (add after step 3 and redeploy)
   - agent: Neon plain URL, `GOOGLE_API_KEY`,
     `BACKEND_BASE_URL=https://recovery-backend.onrender.com`
3. Deploy; check `https://recovery-backend.onrender.com/api/health` and
   `https://recovery-agent.onrender.com/health` (expect `durable_checkpoints: true`).

Free-tier caveat: services sleep after ~15 min idle and take ~1 min to wake.
Open both health URLs before a demo. The 60s retry scheduler only ticks while
the backend is awake.

## 3. Vercel (frontend)

1. vercel.com → Add New → Project → import the repo.
2. **Root Directory: `frontend`** (framework auto-detected: Vite).
3. Environment variable: `VITE_API_BASE=https://recovery-backend.onrender.com`
   (build-time; hash routing means no rewrite config is needed).
4. Deploy → note your `https://<app>.vercel.app` URL → set it as
   `FRONTEND_ORIGIN` on the Render backend and redeploy it (CORS).

## 4. Razorpay webhook → live flow

Dashboard (Test Mode) → Webhooks → Add:
- URL: `https://recovery-backend.onrender.com/webhook/razorpay`
- Secret: your `RAZORPAY_WEBHOOK_SECRET`
- Events: `payment.failed`, `payment_link.paid`, `order.paid`

No tunnel needed any more — Render's URL is public. Fail a test payment with an
error-simulation card and watch the case appear on the Vercel dashboard.

## 5. Seeding demo data in the cloud

The batch runner writes the demo metrics. Easiest: run it once locally against
Neon, or as a one-off on Render (service → Shell):

```
java -jar target/recovery-backend-0.1.0.jar \
  --recovery.batch.enabled=true --recovery.batch.include-agent=true \
  --server.port=9090
```

(needs the agent service up; the image carries data/cases.jsonl
— set CASES_FILE if you move it.)

## Security notes for the live deploy

- All secrets live in Render/Vercel env settings, never in the repo.
- `/internal/tools/**` is protected by AGENT_SHARED_SECRET; keep it long/random
  since the backend is now on the public internet.
- CORS stays locked to your exact Vercel origin.
