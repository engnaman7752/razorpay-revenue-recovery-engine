# How the simulation works

The evaluation never touches Razorpay. It replays 300 pre-generated failed
payments against a deterministic simulator, so every strategy sees exactly the
same world and the comparison is fair and reproducible.

## 1. The dataset (`data/generate.py`, seed 42)

300 cases, distribution fixed by the spec: 35% `insufficient_fund`,
20% gateway/timeout, 15% card declined/disabled, 10% each of
`authentication_failed`, `payment_cancelled`, `card_number_invalid`.
Amounts are log-normal, ₹200–₹80,000, with ~8% above ₹25,000 so the
escalation path gets exercised. 2% of customers are opted out.

The important field is the hidden answer key:

```json
"ground_truth": {"recoverable": true, "recovers_if": "schedule_retry_24h"}
```

`recovers_if` names the **one** action that would have recovered that payment.
`null` means nothing would have. Which action a case gets is drawn per cause
with probabilities close to (but not identical to) the agent's priors — so the
agent can learn the world, but is not handed it.

## 2. The simulator (`SimulatedGateway.java`)

One rule:

```
action succeeds  ⟺  action == ground_truth.recovers_if
```

No randomness at execution time, so the same dataset always produces the same
numbers. Time is collapsed: a "retry in 24h" resolves immediately.

The agent never sees `ground_truth`. It only learns what the simulator returns
after each action — success or failure — exactly like production.

## 3. The four strategies (`BatchRunner.java`)

Each runs over a freshly reloaded copy of all 300 cases:

| Strategy | Behaviour | Purpose |
|---|---|---|
| DO_NOTHING | never acts | the floor — what the merchant loses today |
| NAIVE | `retry_now` ×3 on every case | what a cron job would do |
| **AGENT** | the full LangGraph loop | the system under test |
| ORACLE | reads `ground_truth`, plays the one right action | the ceiling |

Oracle still honours opt-out — a perfect player is still policy-compliant.
AGENT runs last so its cases and decision log are what remains in the database
for the dashboard, and the learning table is reset to priors first so the
learning curve measures this run only.

## 4. What one AGENT case looks like

1. **diagnose** — `insufficient_fund` → `SOFT_DECLINE` (dictionary lookup).
2. **decide** — rank actions by
   `EV = P(recovery|cause,action) × amount − contact_penalty − action_cost`.
   For SOFT_DECLINE, `schedule_retry_24h` (p≈0.55) beats `retry_now` (p≈0.15).
   If the best EV is below the floor, the case is closed as
   `abandoned: EV below threshold` — a logged decision, never a silent drop.
3. **guard** — policy-as-code: attempt/contact caps, quiet hours, opt-out,
   ₹25,000 approval line. A veto removes that action and sends it back to
   decide (at most twice); a hard stop closes the case.
4. **execute** — calls the backend tool, which asks the simulator.
5. **check_outcome** — recovered → close; failed → decide again with that
   action struck off.

Every step writes a `decision_log` row, which is what the case timeline in the
dashboard renders.

## 5. Learning

Each outcome updates a Beta(α, β) posterior for that (cause, action) pair in
`ev_stats`. The backend ships the current counts to the agent on every
`/decide`, so probabilities drift toward the truth as the batch proceeds. It
shows up as **efficiency**, not raw recovery: contacts per ₹10k recovered fell
1.93 → 1.64 → 1.45 across the three hundreds in the reference run.

## 6. Reading the result

```
DO_NOTHING  ₹0
NAIVE       ₹4,65,450   30.2% of oracle, 770 payment attempts
AGENT       ₹15,36,967  99.7% of oracle, ~320 attempts, 254 contacts
ORACLE      ₹15,41,589  100%,            177 attempts,  52 contacts
```

The honest reading: recovery is near-ceiling because a deterministic
one-right-answer simulator is nearly exhaustible within four decide loops.
The real gap is **cost** — the agent spends ~5× the oracle's contacts, and
that is the number the learning system moves.

## 7. Live mode is the same graph

With `GATEWAY_MODE=live`, `LiveRazorpayGateway` replaces the simulator and
calls the real test-mode API. The difference: creating an order or payment
link does not recover money, so those return **PENDING** — the case stays open
and a `order.paid` / `payment_link.paid` webhook settles it later. Pending
outcomes teach the learning table nothing, because nothing has happened yet.
