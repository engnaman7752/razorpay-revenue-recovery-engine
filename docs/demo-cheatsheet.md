# Demo cheat sheet — keep this open on your second screen

## Say this if someone asks "what did you build?" (30 seconds)

> "When a customer's payment fails, most companies just retry it three times
> or give up. But failures have different causes. If it failed because of
> insufficient funds, retrying now fails again — you should retry tomorrow.
> If the card is disabled for online payments, retrying is pointless forever
> — you should send a payment link so they can use another card.
>
> My system reads the failure reason, picks the action most likely to recover
> that specific amount, stops when chasing costs more than it's worth, and
> asks a human before touching anything above ₹25,000.
>
> Against the same 300 failed payments: a normal retry loop recovers
> ₹4.6 lakh. Mine recovers ₹15.4 lakh — with half the payment attempts."

## Three things a retry loop cannot do (your whole pitch)

1. **Knows why** — classifies the root cause, so wait / retry / send-a-link
   are treated as different problems.
2. **Knows when to stop** — abandons low-value cases with a written reason,
   never contacts an opted-out customer, escalates big amounts to a human.
3. **Can prove it** — every decision saved with the numbers behind it.

## Numbers to memorise

| | |
|---|---|
| At risk | ₹23.5 lakh, 300 cases |
| Do nothing | ₹0 |
| Normal retry ×3 | ₹4.65 lakh — 770 attempts |
| **My agent** | **₹15.4 lakh — 3.3× more, half the attempts** |
| Perfect play (cheating) | ₹15.4 lakh — I'm at 99.7% |
| Learning | wasted contacts down 25% across the batch |
| Governance | 26 escalations · 81 blocks · 48 stopped early · 6 opted-out untouched |

## Live demo — 3 screens, in this order

**1. Dashboard** — "₹15.4 lakh recovered of ₹23.5 lakh at risk. This bar is a
player that cheats and sees the answers; I'm at 99.7% of it."

**2. One case timeline** ← *your best screen, spend the most time here*
- "It classified the error — that's a dictionary, not the AI, so it's auditable."
- "It scored every option. Payment link 122,000. Retry 5,000 — a disabled card
  doesn't fix itself."
- "That failed, so it looped back and tried the next best."
- *(point at red)* "Here the system blocked its own agent for hitting a limit."
- **Key line:** "The AI picks from these ranked options. It cannot invent one,
  and it cannot break a safety rule — those run in code after it answers."

**3. Approvals** — click Approve.
- "Above ₹25,000 it stops and waits for a human. Approving resumes it from
  where it paused — and that pause is stored in the database, so it survives
  the server restarting."

## "Anyone can claim 3.3× — prove it" ← run these LIVE

Numbers on a slide are worthless. These compute in front of the judges.
Run from the `agent` folder with the venv active.

### 1. One payment, both approaches (~5 seconds) — your strongest 30 seconds

```powershell
cd agent
python ..\scripts\prove.py case
```

Shows the cron job retrying a dead card three times and recovering ₹0, then
the agent scoring every option with real probabilities and recovering the
money. Say: *"Same payment. Same simulator. That is the whole idea."*

Let a judge choose the case themselves — un-fakeable:

```powershell
python ..\scripts\prove.py case --pick
```

### 2. All 300 cases, computed live (~45 seconds)

```powershell
python ..\scripts\prove.py batch
```

Prints progress as it goes, then the full table. Talk over it while it runs.
Say: *"Nothing cached — it is running the real agent on all 300 right now."*

### 3. Change the rules live (~20 seconds) — proves it is not a recording

Open `agent/policy.yaml`, change `max_payment_attempts: 3` to `1`, save, and
re-run a case. The policy file is re-read on every decision, so the guard
blocks earlier immediately — no restart. Say: *"Governance is a config file
enforced in code, not a paragraph in a prompt."*

### 4. Kill the agent mid-approval (~30 seconds)

With a case waiting in Approvals, restart the agent (`docker compose restart
agent`, or Ctrl-C and start it again), then click Approve. It resumes from the
Postgres checkpoint. Say: *"That pause survived the process dying."*

### If someone still doubts the number

- Open `data/generate.py` — the answer key is generated with a fixed seed
  before any strategy runs.
- Open `SimulatedGateway.java` — the whole simulator is one comparison, and
  the agent never sees the answer key.
- Point at the "perfect play" row: *"That player cheats and reads the answers.
  If my simulator were rigged in my favour, I would beat it. I do not."*

## "Where is Razorpay actually used?" ← expect this question

Be straight about it. The layered answer:

1. **The whole design is Razorpay's model.** The failure reasons the agent
   classifies (`insufficient_fund`, `card_disabled_for_online_payments`,
   `payment_timed_out`…) are Razorpay's real error codes, not invented ones.
   The six actions map to Razorpay Orders and Payment Links. The webhook
   events are `payment.failed`, `payment_link.paid`, `order.paid`.
2. **Live mode calls the real API**, selected by one environment variable —
   `LiveRazorpayGateway` creates real orders and payment links, and
   `RazorpayWebhookController` verifies signatures with HMAC-SHA256 over the
   raw request bytes (there is a unit test proving a re-serialised payload
   fails, which is the bug most teams ship).
3. **The 300-case benchmark deliberately does NOT touch Razorpay**, because
   measuring a strategy needs a deterministic, repeatable world. You cannot
   compare four strategies fairly against a live gateway.

Then prove point 2 on the spot:

```powershell
python scripts\razorpay_smoke.py
```

It authenticates with your test keys, creates a real order, creates a real
payment link, and prints an `https://rzp.io/...` URL. **Open it in a browser
during the demo** — a genuine Razorpay checkout page for a payment your agent
decided to send. That single screen kills the "is this really Razorpay?"
doubt in ten seconds.

For the full inbound loop (webhook → case → recovered) you also need a public
URL; see `docs/phase6-live-demo.md`.

## Hard questions → answers

**"Is the AI actually doing anything, or is it just math?"**
> "The maths ranks the options; the model makes the final pick using context
> the maths misses, like customer history. And the safety limits are pure
> code — the model cannot override them. That's the design, not a limitation."

**"Why is 99.7% so high? Sounds fake."**
> "Good catch — my simulator has one correct action per case, which makes it
> nearly searchable, so I don't lean on that number. The honest metric is
> cost: I spend five times the contacts a perfect player would, and that gap
> is what the learning system closes — 25% better across the batch."

**"Does it really work with Razorpay or just simulate?"**
> "Same code path, live test mode, one environment variable. Webhook
> signatures verify against the raw request bytes, and I have a unit test
> proving the common shortcut — re-serialising the JSON — fails."

**"What would break in production?"**
> "No retry-backoff on the Razorpay API, a single-instance scheduler, and no
> idempotency keys on order creation. All listed in my README."

## Before you present

- [ ] Services up, batch already run (dashboard not empty)
- [ ] **At least one case still unapproved** in the Approvals queue
- [ ] Case-detail tab pre-opened — pick a hard decline with a red blocked row
- [ ] `.env` not visible anywhere; notifications off
- [ ] Backup ready: `python frontend/dev-mock-api.py` + `npm run dev`
      (full UI, real agent decisions, no Java or database needed)
