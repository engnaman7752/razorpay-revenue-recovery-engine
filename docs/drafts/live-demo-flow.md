# The live demo — in the order you'll narrate it

This is the flow you described: first explain the process (which file, how the
nodes connect), then show a REAL failed transaction on Razorpay's test screen,
then the model working on it, then the dashboard. End to end, live.

Keep `docs/architecture-flow.html` open in a browser tab — it's the picture you
point at during Part 1.

---

## Before you record (one-time, ~10 min)

The real failed-transaction step needs Razorpay to reach your laptop, so:

1. `.env` → `GATEWAY_MODE=live`, restart the backend
2. Start the tunnel:  `ngrok http 8081`  (leave it running)
3. `python scripts\webhook_setup.py url` → paste the URL + secret into
   Razorpay Dashboard → Settings → Webhooks. Tick `payment.failed`,
   `payment_link.paid`, `order.paid`
4. `python scripts\dryrun.py` → confirms everything is green

Have these tabs open, in this order:
- **Tab 1** — `docs/architecture-flow.html` (the diagram)
- **Tab 2** — Razorpay test dashboard (Payment Links, so you can create one)
- **Tab 3** — your dashboard `http://localhost:5173`
- **VS Code** — with `graph/build.py` and `policy.yaml` already open

---

## PART 1 · Explain the process (2 min) — point at the diagram

Open Tab 1 (the diagram). Walk boxes 1→8 with your finger/cursor.

> "Before I run it, here's the whole path a failed payment takes. Every box is
> a real file.
>
> A payment fails, Razorpay fires a webhook. My backend verifies the signature —
> over the raw bytes, box 2 — and opens a case.
>
> Now the important part, box 3. The case goes to a **separate agent process**.
> This agent has no database and no gateway — it can decide, but it physically
> cannot move money. The backend does that. Brain and hands, split on purpose.
>
> Inside the agent is this LangGraph loop — diagnose, decide, guard, execute,
> check outcome. Diagnose finds the cause. Decide ranks every action by expected
> value. Guard — box 4 — checks policy, and nothing reaches the gateway without
> passing it. If it fails, it loops back and tries the next-best action.
>
> Anything over ₹25,000 pauses for a human, box 5, and that pause is saved to
> Postgres so it survives a restart. Every single step is logged, box 7, and the
> probabilities learn from every outcome. Box 8 — the dashboard — shows all of
> it. Now let me actually run it."

Switch to VS Code, show `graph/build.py` for 10 seconds:

> "And here's that loop as actual code — the nodes, and how they're wired
> together. This one file is the whole decision flow."

---

## PART 2 · A real failed transaction on Razorpay (1 min)

Switch to Tab 2 (Razorpay test dashboard).

> "This is Razorpay test mode — real API, no real money. I'll create a payment
> and fail it on purpose."

**On screen, do this:**
1. Create a Payment Link (any amount under ₹25,000 — say ₹4,999) — or reuse one
2. Open the link's checkout page
3. Choose **UPI**, enter the test id **`failure@razorpay`**, submit
4. The checkout shows the payment **failing** — that's your real failed
   transaction, on Razorpay's own screen

> "There it is — a real failed payment. Razorpay just fired a `payment.failed`
> webhook at my backend. Watch what happens."

> **Tip:** keep the backend terminal visible in a corner. The instant the
> webhook lands you'll see `LIVE case … opened for failed payment pay_…`.
> Catching that live is a great moment.

---

## PART 3 · The model works the case (1.5 min)

Switch to Tab 3 (your dashboard) → **Cases** → the new case at the top → open it.

> "My system already picked it up. This is the decision timeline — and this is
> not a log I wrote for the demo, it's the real audit trail from the database."

Scroll slowly, narrate each row:

> "Diagnose — it read Razorpay's error reason and mapped it to a cause.
>
> Decide — here's the expected-value ranking it saw, every option scored. It
> picked the top one.
>
> Guard — the policy check.
>
> Execute — and look: it created a **real Razorpay payment link**. That rzp.io
> URL is live. The agent chose to send the customer a fresh link, and it made a
> real one through Razorpay's API."

If a row says `fallback_error`:

> "And see this — the LLM call failed on this case, so it fell back to the pure
> math and still made the right call, and logged that it fell back. The model
> ranks; it isn't the decision-maker. The system works even when the model is
> down."

---

## PART 4 · Close the loop — recovery (1 min)

Two ways. Pick one.

**Option A — fully live (strongest, if the tunnel is stable):**
Open the rzp.io link from the timeline, pay it with UPI **`success@razorpay`**.

> "I'll pay the link the agent sent — success this time."

Razorpay fires `payment_link.paid` → refresh the dashboard → **RECOVERED**.

**Option B — fire the paid-webhook yourself (safe, no wifi risk):**
```powershell
python scripts\webhook_setup.py pay <case-id>
```
> "I'll fire the paid-webhook locally so this doesn't depend on the wifi — same
> signed payload Razorpay sends."

Either way, then say the line that matters:

> "Notice — when the agent created that link, the outcome was **pending**, not
> recovered. Creating a link doesn't recover money. Only the payment webhook
> can close the case. Most systems count the optimistic number. Mine doesn't."

Refresh → the case is **RECOVERED**. 

---

## PART 5 · The dashboard — the scale (1.5 min)

Dashboard home. The strategy table.

> "That was one case, live. Here's all 300 from the benchmark. Do-nothing
> recovers zero. Naive retrying — three tries on everything — gets ₹4.65 lakh
> across 770 attempts. My agent gets **₹15.37 lakh** using 316 attempts. 3.3×
> the money, less than half the attempts. The oracle, perfect play, gets
> ₹15.41 lakh — I land at 99.7% of a player that reads the answer key."

Then the honest caveat (this wins marks):

> "One honest note on that 99.7%: the benchmark has one right answer per case,
> so recovery is nearly exhaustible. The number I actually defend is the cost
> side — the agent spends far fewer contacts than naive, and the learning system
> keeps cutting that. If I only showed you the recovery number, I'd be
> overselling it."

Close:

> "So — a decision problem, not a retry problem. Expected value picks the
> action, policy-as-code constrains it, a human approves anything expensive,
> every decision is on the record, and it's really Razorpay end to end. Thank
> you."

---

## If the tunnel dies mid-demo

Don't panic, don't restart everything. Fall back instantly:

- Skip Part 2's live failure → use `python scripts\webhook_setup.py selftest
  --reason card_declined`. It opens the same kind of case with a real link,
  no tunnel needed. Say "I'm simulating the inbound webhook locally" — still
  honest, still a real Razorpay link in the result.
- Everything else (Parts 3–5) is unaffected.

## Order to actually record
Record Part 1 (diagram + code) and Part 5 (dashboard numbers) FIRST — they need
no live state and can't break. Then do the live Parts 2–4 as one continuous
take. If 2–4 fumble, you re-record only those, not the whole thing.
