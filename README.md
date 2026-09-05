# AI Revenue Recovery Engine

> **Razorpay Hackathon · Track 03** — recovering revenue lost to failed payments by treating it as a **decision problem under uncertainty**, not a retry loop.

An autonomous agent that, for every failed payment, answers one question — *given why this specific payment failed, what is the single best next action, and is it even worth taking one?* — then executes it under **policy-as-code governance**, with a **human in the loop** for high-value cases and **every decision on an audit trail**.

<p>
<img alt="Java 17" src="https://img.shields.io/badge/Java-17-orange">
<img alt="Spring Boot" src="https://img.shields.io/badge/Spring%20Boot-3.3-brightgreen">
<img alt="Python" src="https://img.shields.io/badge/Python-3.11-blue">
<img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-state%20machine-purple">
<img alt="React" src="https://img.shields.io/badge/React%2BVite-frontend-06b6d4">
<img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-durable%20state-336791">
<img alt="Tests" src="https://img.shields.io/badge/tests-46%20passing-success">
</p>

---

## TL;DR — the result

On 300 synthetic failed payments (₹23.5L at risk, deterministic replay, seed 42):

| Strategy | Recovered | % of ceiling | Payment attempts | Customer contacts |
|---|--:|--:|--:|--:|
| Do nothing | ₹0 | 0% | 0 | 0 |
| Naive (retry ×3 always) | ₹4,65,450 | 30% | 770 | 0 |
| **This agent** | **₹15,36,967** | **99.7%** | **316** | 254 |
| Oracle (reads the answer key) | ₹15,41,589 | 100% | 125 | 52 |

**3.3× the recovery of naive retrying, with less than half the payment attempts** — and it abandons hopeless cases with a *logged reason* instead of hammering the gateway. It reaches 99.7% of a player that can see the hidden answer key.

---

## The problem

When a payment fails, most systems do one of two things: nothing, or blindly retry on a cron until it works or the customer churns. Both treat every failure identically — but *"insufficient funds"*, *"expired card"*, and *"gateway timed out"* are completely different problems. Retrying an expired card three times recovers nothing; it just burns processor fees and trains the customer to ignore you.

Recovery is really a **portfolio decision**: which rupees to chase, with which action, and when to stop. That framing is the whole project. Everything else is the infrastructure that lets an agent make that decision *safely*.

---

## Architecture

Three services, and the split between them is the core design decision: **the thing that reasons and the thing that acts are separate processes.**

```mermaid
flowchart LR
    subgraph FE["Frontend · React + Vite"]
        UI["Dashboard · Cases · Approvals<br/>renders the audit trail live"]
    end

    subgraph BE["Backend · Spring Boot / Java 17"]
        API["REST API /api/**"]
        TOOLS["6 tool endpoints<br/>/internal/tools (X-Agent-Secret)"]
        WH["Webhook receiver<br/>HMAC over raw bytes"]
        GW["Gateway: Simulated or LiveRazorpay"]
        LOG["DecisionLogger → decision_log"]
    end

    subgraph AG["Agent · Python FastAPI + LangGraph"]
        GRAPH["Decision graph<br/>diagnose → decide → guard → execute"]
        LEARN["Beta-Bernoulli learning"]
    end

    DB[("PostgreSQL<br/>cases · decision_log · ev_stats<br/>LangGraph checkpoints")]
    RZP["Razorpay Test API"]

    UI -->|/api| API
    API --> DB
    WH -->|payment.failed| API
    API -->|POST /decide| GRAPH
    GRAPH -->|6 HTTP tools| TOOLS
    TOOLS --> GW
    GW --> RZP
    RZP -->|order.paid / link.paid| WH
    TOOLS --> LOG
    LOG --> DB
    GRAPH -.checkpoints.-> DB
    LEARN -.posteriors.-> DB
```

**Separation of powers, on purpose:**

- **Backend owns reality** — Razorpay calls, webhook receipt + HMAC verification, the database of record, the retry scheduler, the REST API, and the *six* tool endpoints the agent is allowed to use. It is the only thing that can move money.
- **Agent owns the decision graph only.** It holds no database connection and cannot call Razorpay. Its "hands" are six authenticated HTTP tools. An agent that misbehaves still cannot do damage, because **the permission boundary is the network between two services, not a line in a prompt.**
- **Frontend** renders the money, the cases, the full decision timeline, and the human approval queue — reading the real `decision_log`, so what a reviewer sees *is* the audit trail.

### The decision graph (LangGraph state machine)

```mermaid
flowchart TD
    A[diagnose] --> B[decide]
    B --> C{guard}
    C -->|ok| D[execute]
    C -->|veto, max 2| B
    C -->|hard stop / EV too low| F[close]
    C -->|over ₹25,000| E[escalate_notify]
    E --> H[human_review ⏸]
    H -->|approved| B
    H -->|rejected| F
    D --> G{check_outcome}
    G -->|recovered / pending| F
    G -->|failed| B
    F --> Z([END])
```

| Node | What it does | Why it's built this way |
|---|---|---|
| **diagnose** | Razorpay `error_reason` → cause (SOFT/HARD decline, TRANSIENT, CUSTOMER_ACTION, UNRECOVERABLE) | A deterministic dictionary, **not the LLM** — you don't let a model hallucinate a fact you already know |
| **decide** | Ranks actions by **EV = P(recovery \| cause, action) × amount − contact_penalty − action_cost**; the LLM picks among *viable* options only | P comes from a learned Beta-Bernoulli posterior; the LLM adds judgment but **cannot invent an action the economics didn't approve** |
| **guard** | Reads `policy.yaml`: attempt/contact caps, quiet hours, opt-out, the ₹25,000 line | Pure code. **The LLM cannot bypass any of it** — a veto re-routes to decide, a hard stop closes the case |
| **execute** | Calls a backend tool → the gateway (simulated or real Razorpay) | Live actions return **PENDING**, never "recovered" — only a webhook settles money |
| **human_review** | Pauses on a LangGraph `interrupt()`, checkpointed to Postgres | The pause **survives an agent restart** — approval resumes the graph from its checkpoint |

Every node writes the exact inputs it saw, the action, the reasoning, the EV, and every block-with-reason to `decision_log`. **The agent physically cannot act without logging.**

---

## Key engineering decisions

The parts I'd want to talk through in an interview:

1. **Reasoning and acting are different processes.** The agent can't touch the database or Razorpay; it can only call six authenticated tools. Security by architecture, not by prompt.
2. **Expected value is the decision-maker; the LLM is a ranker.** The system is *correct even when the model is down* — a Gemini outage falls back to the deterministic EV ranking and logs that it did. (This literally happened during development and the agent kept recovering money.)
3. **Governance is policy-as-code, not instructions.** Every hard limit lives in `policy.yaml`, enforced by the backend. You can change policy without touching code, and no amount of clever prompting gets the agent past it.
4. **Human-in-the-loop that survives a crash.** High-value cases pause on a durable Postgres checkpoint — kill the process, restart it, the case is still waiting for approval.
5. **The benchmark is a deterministic replay, on purpose.** Comparing four strategies is only fair if all four face an identical world; randomness would measure luck. The *real-time* path (live Razorpay webhooks) is separate and demonstrated.
6. **Honest measurement.** The headline number is qualified in the README itself (see limitations) — the differentiator is cost-efficiency, and the code says so.

---

## Results in detail

Total at risk: **₹23,53,507**. Reproduce with a single command (see below).

**It learns** — Beta-Bernoulli posteriors update during the run. Recovery stays flat; wasted outreach drops **25%** as the agent prunes actions whose true success rate is near zero:

| Cases | Recovered | Contacts per ₹10k recovered |
|---|--:|--:|
| 1–100 | 59 | 1.93 |
| 101–200 | 59 | 1.64 |
| 201–300 | 55 | **1.45** |

**Governance during the run:** 26 escalations (every case above ₹25,000 paused for a human), 180 stopping-rule activations (guard vetoes + EV-abandonment closes), and all 6 opted-out customers left completely untouched (0 actions). Full breakdown per failure cause: [`eval/results.md`](eval/results.md).

---

## Tech stack

| Layer | Stack |
|---|---|
| **Agent** | Python 3.11, FastAPI, **LangGraph** state machine, Gemini (temperature 0, JSON-only) with deterministic fallback, Beta-Bernoulli learning, `PostgresSaver` checkpoints |
| **Backend** | Java 17, **Spring Boot 3.3**, Flyway migrations, HikariCP, JPA, Razorpay REST integration, HMAC-SHA256 webhook verification |
| **Frontend** | React + Vite, Tailwind, Recharts, dark mode |
| **Data** | PostgreSQL — cases, `decision_log`, `ev_stats`, LangGraph checkpoints |
| **Quality** | 46 pytest tests + JUnit, deterministic seeded fixtures, one-command CI (`ci/verify.sh`) |

---

## Run it

```bash
cp .env.example .env          # all config is environment-only; no secrets in code
docker compose up --build
# frontend  http://localhost:5173
# backend   http://localhost:8080/api/health   (port via SERVER_PORT)
# agent     http://localhost:8000/health
```

**Reproduce the benchmark** (regenerates `eval/results.md` + `/api/metrics`):

```bash
java -jar backend/target/recovery-backend-0.1.0.jar \
  --recovery.batch.enabled=true --recovery.batch.include-agent=true
```

**Live Razorpay test mode** (real API, real webhooks, no real money): see [`docs/razorpay-manual.md`](docs/razorpay-manual.md).

---

## Testing

46 Python tests + JUnit, covering the parts that actually matter:

- the full 300-case graph loop against a mock backend
- every guardrail (caps, quiet hours, opt-out, escalation line)
- the LLM chooser including *every* fallback path (bad reply, API error, no key)
- human-in-the-loop **restart survival** (pause, kill, resume from checkpoint)
- live-mode PENDING semantics (an action initiated ≠ money recovered)
- webhook **HMAC verification over raw bytes** — with a test proving re-serialized-but-equal JSON is rejected

```bash
cd agent && python -m pytest tests/      # 46 tests
cd backend && mvn test                   # JUnit (signature verifier)
bash ci/verify.sh                        # everything, what CI runs
```

---

## Security

- Webhook HMAC-SHA256 verified against the **raw request body bytes** (never re-serialized JSON), constant-time compare, 401 on mismatch — with a unit test proving a re-serialized-but-identical payload fails.
- `/internal/tools/**` requires `X-Agent-Secret` (constant-time check) and has no CORS mapping; public CORS covers `/api/**` only.
- All secrets are environment-only; none appear in any file or log. Live keys are refused unless prefixed `rzp_test_`.

---

## Reproducibility

Everything is seeded and pinned: the case generator (seed 42, exact distribution), the simulator (an action succeeds *iff* it equals `ground_truth.recovers_if`), the LLM (temperature 0 + deterministic fallback), the batch clock (fixed noon IST so quiet-hours never flap), and the learning table (reset to priors before each AGENT run). **Two runs produce the same numbers.**

---

## Honest limitations

Kept in the README on purpose — knowing what your numbers *don't* prove is the point.

- **The simulator is deterministic and single-shot.** One action recovers each case; real outcomes are stochastic and time-dependent. That's why recovery reaches 99.7% of oracle — it's near-exhaustible. **The truer differentiator is efficiency:** the agent spends ~5× the oracle's contacts, and that gap — not the recovery headline — is what the learning system narrows.
- **Priors are hand-set near the generator's truth**, so learning shows up mostly as pruning genuinely-useless actions. With mis-specified priors it would matter more.
- **The LLM adds judgment, not magic.** With clean EV rankings the deterministic fallback picks the same action most of the time; the LLM earns its place on tie-breaks and customer context — and the batch runs identically without an API key, by design.
- **Live mode is demonstrated, not hardened:** no retry/backoff on Razorpay calls, single-instance scheduler, no idempotency keys on order creation, webhook replay handled only by payment-id dedupe.
- **One merchant, one currency, no dashboard auth** — explicitly out of scope for the hackathon.

---

## Repository map

```
agent/       LangGraph decision graph, EV + learning, policy.yaml, 46 tests
backend/     Spring Boot: API, tools, gateway, webhook, batch runner, migrations
frontend/    React dashboard — cases, decision timeline, approvals
data/        seeded case generator + 300-case dataset (ground truth)
eval/        verified benchmark results
docs/        architecture, live-demo, simulation write-ups
scripts/     live-proof + demo tooling (webhook harness, dry-run, benchmark)
ci/          one-command verification
```
