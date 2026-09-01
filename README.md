# AI Revenue Recovery Engine

**Razorpay Hackathon — Track 03**

Every failed payment is revenue on the floor. This system treats getting it back
as a **portfolio decision problem — which rupees to chase, how, and when to
stop — executed under policy-as-code governance.** An LLM helps choose the next
action, but every hard limit lives in code, every decision is audited, and
high-value cases wait for a human.

## Results — 300-case synthetic batch (seed 42, deterministic simulator)

| Strategy | Recovered ₹ | % of oracle | Cases | Contacts | Contacts per ₹10k | Payment attempts |
|---|---|---|---|---|---|---|
| DO_NOTHING | ₹0 | 0% | 0 | 0 | – | 0 |
| NAIVE (retry ×3 always) | ₹4,65,450 | 30.2% | 65 | 0 | – | 770 |
| **AGENT** | **₹15,36,967** | **99.7%** | 173 | 254 | 1.65 | ~320 |
| ORACLE (perfect play) | ₹15,41,589 | 100% | 177 | 52 | 0.34 | 177 |

Total at risk: ₹23,53,507. The agent recovers **3.3× what naive retrying does**
with **less than half the payment attempts**, and abandons low-EV cases with a
logged reason instead of silently dropping them.

**Learning curve** (Beta-Bernoulli posteriors updating during the batch —
same recovery, less wasted outreach):

| Cases | Recovered | Contacts per ₹10k recovered |
|---|---|---|
| 1–100 | 59/61 recoverable | 1.93 |
| 101–200 | 59/60 | 1.64 |
| 201–300 | 55/58 | 1.45 |

Governance during the batch: 26 escalations (every case above ₹25,000), 81
guard blocks, 48 EV-abandonments, all 6 opted-out customers untouched (0
actions). Full details: [`eval/results.md`](eval/results.md).

## Architecture

```
frontend (React+Vite) ──► backend (Spring Boot, Java 17) ◄──► agent (Python FastAPI + LangGraph)
                               │                                    │
                         Razorpay test API                   PostgresSaver checkpoints
                               └───────────── PostgreSQL ───────────┘
```

Separation of powers, on purpose:

- **backend** owns reality: Razorpay calls, webhook receipt + HMAC verification,
  the database of record, the retry scheduler, the REST API for the UI, and the
  six tool endpoints the agent is allowed to use.
- **agent** owns the decision graph ONLY. It never calls Razorpay and never
  writes business tables. Its hands are six HTTP tools on the backend,
  authenticated with `X-Agent-Secret`.
- **frontend** shows the money, the cases, the full decision timeline, and the
  human approval queue.

### The decision graph (LangGraph)

```
diagnose ─► decide ─► guard ─► execute ─► check_outcome ─► (decide | close)
              ▲          │
              │          ├─► close            (EV below threshold, limits hit)
              │          └─► escalate_notify ─► human_review ⏸ ─► (decide | close)
              └── veto (max 2 re-decides)
```

- **diagnose** — deterministic dict: Razorpay `error_reason` → cause
  (SOFT_DECLINE / TRANSIENT / HARD_DECLINE / CUSTOMER_ACTION / UNRECOVERABLE).
  Not the LLM's job.
- **decide** — actions ranked by expected value:
  `EV = P(recovery|cause,action) × amount − contact_penalty − action_cost`,
  with P from a Beta-Bernoulli posterior that learns from every outcome.
  Gemini (temperature 0, JSON-only) makes the final pick **among viable
  actions only**; one retry on a bad reply, then a logged fallback to top-EV.
  Cases whose best EV is below the threshold are closed as
  `abandoned: EV below threshold` — a logged decision, not a silent drop.
- **guard** — pure Python reading `policy.yaml` (hot-reloadable): attempt caps,
  contact caps, quiet hours (Asia/Kolkata), opt-out = immediate stop, decide-loop
  budget, and the ₹25,000 auto-escalation line. Vetoes re-route to decide (max
  2), hard stops close the case. **The LLM cannot bypass any of this.**
- **human_review** — cases above ₹25,000 pause on a LangGraph `interrupt()` with
  checkpoints in Postgres. The pause **survives an agent restart**; approval via
  the dashboard (or `POST /api/escalations/{id}/resolve`) resumes the graph from
  its checkpoint.
- Every node writes to `decision_log`: the exact inputs seen, the action, the
  reasoning, the EV, and every block with its reason.

## Run it

```bash
cp .env.example .env        # fill in secrets (all config is env-only)
docker compose up --build
# frontend  http://localhost:5173
# backend   http://localhost:8080/api/health
# agent     http://localhost:8000/health
```

**Batch evaluation** (regenerates `eval/results.md` + `/api/metrics`):

```bash
java -jar backend/target/recovery-backend-0.1.0.jar \
  --recovery.batch.enabled=true --recovery.batch.include-agent=true
```

**Tests** — 45 Python tests (guardrails, LLM chooser incl. fallbacks, the full
300-case graph loop, human-in-the-loop restart survival, live PENDING semantics)
plus JUnit tests for webhook signature verification:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r agent/requirements.txt
cd agent && python -m pytest tests/
cd backend && mvn test
```

**Everything at once** (what CI runs on every push): `bash ci/verify.sh`

**UI without the JVM** (demo rehearsal): `python frontend/dev-mock-api.py` then
`cd frontend && npm run dev` — real graph decisions behind every page.

**Live Razorpay test mode**: see [`docs/phase6-live-demo.md`](docs/phase6-live-demo.md)
(test keys, webhook tunnel, error-simulation cards, link-paid recovery).

## Reproducibility

Everything is seeded and pinned: the case generator (seed 42, exact
distribution counts), the simulator (deterministic: an action succeeds iff it
equals `ground_truth.recovers_if`), the LLM (temperature 0, with a
deterministic fallback), the batch clock (fixed noon IST so quiet-hours checks
never flap), and the learning table (reset to priors at the start of each AGENT
run). Two runs of the batch produce the same numbers.

## Security

- Webhook HMAC-SHA256 verified against the **raw request body bytes** (never
  re-serialized JSON), constant-time compare, 401 on mismatch — with a unit
  test proving that re-serialized-but-equal JSON fails.
- All secrets come from environment variables only (`.env.example` provided);
  no secret appears in any file or log.
- `/internal/tools/**` requires `X-Agent-Secret` (constant-time check, 401
  otherwise) and has no CORS mapping; public CORS covers `/api/**` only.

## Honest limitations

- **The simulator is deterministic and single-shot.** Real recovery outcomes
  are stochastic and time-dependent; our ground truth model (one action
  recovers, all others fail) makes near-exhaustive search possible, which is
  why AGENT reaches 99.7% of oracle. The truer differentiator is efficiency:
  the agent needs ~5× the oracle's contacts, and that gap — not the recovery
  headline — is what the learning system actually narrows.
- **Priors are hand-set and close to the generator's truth**, so learning
  shows up mostly as pruning genuinely-useless actions (e.g. reminders for
  hard declines). With mis-specified priors the learning would matter more;
  with 300 cases the posteriors move slowly by design.
- **The LLM adds judgment, not magic.** With clean EV rankings the rule
  fallback picks the same action most of the time; the LLM earns its place on
  tie-breaks and context (customer history), and the batch runs identically
  without an API key by design.
- **Live mode is demonstrated, not hardened**: no retry/backoff on Razorpay API
  calls, single-instance scheduler, no idempotency keys on order creation, and
  webhook replay beyond payment-id dedupe is not handled.
- **One merchant, one currency, no dashboard auth** — explicitly out of scope
  for the hackathon (§13).
