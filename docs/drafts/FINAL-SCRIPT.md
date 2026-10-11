# The final script — record this one

1–1.5 min setup (intro + problem + architecture), 3–3.5 min live simulation,
close. This supersedes the earlier drafts — written for the version that's
actually working now (real webhook, real recovery, LLM live).

**Before recording:** run `python scripts\dryrun.py` once. Confirm the backend
log shows Tomcat on 8081, the agent shows `durable_checkpoints: true`, and
your ngrok tunnel + webhook are registered if you're doing the fully-live
version. Keep `docs/architecture-flow.html` open in a tab.

═══════════════════════════════════════════════════════════════════
PART A — INTRO + PROBLEM + ARCHITECTURE (0:00 – 1:30)
═══════════════════════════════════════════════════════════════════

## 0:00 – 0:15 · Intro
**Screen:** your dashboard home, everything already running.

> "Hi, I'm Shyam. This is an AI revenue recovery engine for Razorpay's Track 3.
> Everything you'll see today is running live on my laptop — nothing
> pre-recorded, no hardcoded numbers."

## 0:15 – 0:45 · The problem
**Screen:** stay on the dashboard.

> "When a payment fails, most businesses do one of two things: nothing, or
> blindly retry it until it works or the customer gives up. Both waste money,
> because they treat every failure the same. But an expired card and a network
> glitch are completely different problems. The real question isn't 'retry
> harder' — it's: given *why* this specific payment failed, what's the single
> best next action, and is it even worth taking one?"

## 0:45 – 1:30 · Architecture, fast
**Screen:** the diagram tab (`architecture-flow.html`). Sweep top to bottom —
don't linger on any one box.

> "Here's how it works. A payment fails — either a real Razorpay webhook or a
> replayed test case. My backend verifies it and hands it to a **separate AI
> agent**. That agent can decide, but it cannot touch money — my backend does
> that, and only after a policy check.
>
> Inside the agent: it diagnoses *why* the payment failed, ranks every possible
> action by expected value — how likely it is to recover the money versus what
> it costs — and picks the best one. A policy gate checks it before anything
> happens. If the amount is over ₹25,000, it pauses for a human. Every single
> decision gets written to an audit log, and the system learns from every
> outcome.
>
> That's the whole architecture. Now let me actually run it."

> Don't read file names out loud — just point and keep moving. 45 seconds max.

═══════════════════════════════════════════════════════════════════
PART B — LIVE SIMULATION (1:30 – 5:00)
═══════════════════════════════════════════════════════════════════

This is the core. Slow down. Let each screen sit for a second before you talk
over it.

## 1:30 – 2:15 · A real failed payment
**Screen:** Razorpay test dashboard → open/create a payment link → pay it with
a test card → click **Failure** on the simulation screen (or Netbanking →
Failure — whichever you rehearsed).

> "This is Razorpay test mode — the real API, no real money. I'll fail a
> payment on purpose... [do it] ...and there it is, a real failed transaction,
> on Razorpay's own screen. That just fired a `payment.failed` webhook straight
> at my backend."

Keep the backend terminal visible in a corner — point at the log line the
moment it appears:
`LIVE case … opened for failed payment pay_…`

## 2:15 – 3:45 · Watch the agent decide — THE CORE
**Screen:** dashboard → Cases → the new case → open it → scroll the decision
timeline slowly.

> "My system already caught it. This timeline is the real audit trail — not a
> log I wrote for the demo, this is the actual `decision_log` table.
>
> First, diagnose: it read the failure reason and worked out the underlying
> cause. Then decide: here's the expected-value ranking it actually saw —
> every option scored by probability of recovery times amount, minus cost. It
> picked the top one. Then guard: the policy check, before anything is
> allowed to happen. Then execute — and here's the real action it took."

**If it retried (gateway/technical-style failure):**

> "It diagnosed this as a transient glitch — a network hiccup, not a real
> decline — so its best move was an immediate retry. It created a real
> Razorpay order and is now waiting for the payment to settle."

**If it sent a payment link (card-decline-style failure):**

> "It diagnosed a hard decline, so retrying does nothing — instead it created
> a real Razorpay payment link. This URL is live, created through their API."

If any row says `fallback_error`:

> "And here — the AI model failed on this step, so the system fell back to
> the pure math and still made the correct call, and logged that it fell
> back. The model ranks options; it isn't the decision-maker. That's why this
> keeps working even when the model API is down."

## 3:45 – 4:15 · Close the loop — recovery
**Screen:** terminal.

```powershell
python scripts\webhook_setup.py pay <case-id>
```

> "Now I'll settle it — this fires the same signed payment-confirmed webhook
> Razorpay would send. [run it] ...and the case is RECOVERED."

Refresh the dashboard, point at the status change.

> "Notice: right up until this moment, the action showed *pending*, not
> recovered. Creating an order or a link doesn't recover money by itself —
> only the payment webhook closes the case. This system never counts money it
> hasn't actually received."

## 4:15 – 4:40 · Governance — human approval
**Screen:** Approvals tab → approve the staged high-value case → watch it
resume.

> "One more thing. Anything above ₹25,000 doesn't get auto-handled — it pauses
> right here and waits for a human. This pause is saved to the database, so
> even if I restart the whole system, the case is still sitting here. I
> approve it... and the agent resumes from exactly where it stopped."

## 4:40 – 5:00 · Numbers + honest close
**Screen:** dashboard strategy table.

> "Across 300 payments: doing nothing recovers zero. Blind retrying gets ₹4.65
> lakh but hits the gateway 770 times. My system recovers **₹15.37 lakh — 3.3
> times as much — using less than half the attempts.**
>
> One honest note: recovery is near the theoretical best because the test set
> has one right answer per case. The real win is efficiency — this needs far
> fewer contacts than naive retrying, and it keeps improving as it learns.
>
> So: a decision problem, not a retry problem, with a human on the expensive
> calls and every step on the record. Thank you."

═══════════════════════════════════════════════════════════════════

## Recording order (not playback order)
1. **Record Part A + the 4:40–5:00 numbers first.** No live state, can't fail,
   gets easy wins in the can.
2. **Record 1:30–4:40 as one continuous live take.** If it fumbles, you only
   re-shoot this block.

## If the live webhook misbehaves mid-take
Don't panic, don't restart services. Fall back instantly:
```powershell
python scripts\webhook_setup.py selftest --reason gateway_technical_error
```
Same result — a real case, worked live, with a case id ready for the `pay`
command. Say "I'm sending the failure webhook locally so this doesn't depend
on the venue wifi" — still fully honest, still shows the same mechanism.

## Legibility checklist
- 1920×1080 set **before** arranging windows
- Chrome zoom 125–150%, terminal font 18+
- Move the mouse slowly; pause 2s after every click
- Record a 20-second throwaway take first and check it back

## Before you submit
- [ ] No secrets visible on screen (`.env`, terminal scrollback, Razorpay keys)
- [ ] Under the time limit
- [ ] Link tested in an incognito window
