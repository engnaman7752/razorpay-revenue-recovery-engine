# The 5-minute video — your structure

1 minute setup (intro + problem + architecture in 20 seconds), then 4 minutes
of the thing actually running. Times are a guide; the second half is the star.

Have ready: the diagram tab (`docs/architecture-flow.html`), Razorpay test
dashboard, your dashboard. Run `python scripts\dryrun.py` first so your cases
are staged.

═══════════════════════════════════════════════════════════════════
PART A — SETUP (0:00 – 1:00)
═══════════════════════════════════════════════════════════════════

## 0:00 – 0:15 · Intro
**Screen:** your dashboard home.

> "Hi, I'm Shyam. This is an AI revenue recovery engine for Razorpay's Track 3.
> Everything you'll see is running live on my laptop — nothing pre-recorded,
> no hardcoded numbers."

## 0:15 – 0:40 · Problem statement
**Screen:** stay on the dashboard.

> "When a payment fails, businesses either do nothing, or blindly retry until
> it works or the customer quits. Both waste money — they treat every failure
> the same. But an expired card and a network glitch are different problems.
> The real question isn't 'retry harder', it's: given *why* this payment failed,
> what's the single best next action — and is it even worth taking one?"

## 0:40 – 1:00 · Architecture, in 20 seconds
**Screen:** the diagram tab. Sweep your cursor top to bottom, don't linger.

> "Quick picture: a failed payment comes in, a separate AI agent decides what to
> do but can't touch money itself — my backend does that, only after a policy
> check. Every decision is logged, it learns from each outcome, and anything
> expensive waits for a human. That's the whole system. Now let me run it."

> Do NOT read the file names aloud. Just wave at the flow and move on. The
> picture does the work; you keep talking.

═══════════════════════════════════════════════════════════════════
PART B — THE SIMULATION, LIVE (1:00 – 5:00)
═══════════════════════════════════════════════════════════════════

This is 80% of your video. Slow down here. Let each screen breathe.

## 1:00 – 1:45 · A real failed payment
**Screen:** Razorpay test dashboard → create/open a payment link → pay with UPI
`failure@razorpay`.

> "This is Razorpay test mode — real API, no real money. I'll fail a payment on
> purpose. [do it] ...and there's the failure, on Razorpay's own screen. That
> just fired a webhook at my system. Watch."

Keep the backend terminal in a corner — when `LIVE case … opened` appears, point at it.

## 1:45 – 3:15 · The agent works the case — THE CORE
**Screen:** your dashboard → Cases → the new case → open it → scroll the timeline slowly.

> "My system already caught it. This timeline is every decision it made — and
> it's the real audit trail, not a demo log.
>
> It worked out why the payment failed. Then it scored every possible action —
> retry now, retry later, payment link, reminder — by how likely each is to
> recover the money versus what it costs, and picked the best. It checked its
> policy rulebook. Then it acted: it created a real Razorpay payment link — this
> URL is live.
>
> And notice the outcome says *pending*, not recovered. Sending a link doesn't
> recover money. Only the customer paying does. It never counts money it
> hasn't actually received."

If any row says `fallback_error`:
> "See here — the AI model failed on this step, so it fell back to the math and
> still got it right, and logged that it did. The model helps rank; it isn't in
> charge. The system works even when the model is down."

## 3:15 – 3:45 · Close the loop — recovery
**Screen:** pay the link with `success@razorpay` (or run
`python scripts\webhook_setup.py pay <case-id>`), then refresh the dashboard.

> "Now the customer pays the new link... and the case closes itself as
> recovered. That's the full loop — a real failed payment, recovered, end to
> end, through Razorpay."

## 3:45 – 4:30 · Governance + human approval
**Screen:** Approvals tab → approve the staged high-value case → watch it resume.

> "One more thing that matters. Anything above ₹25,000 doesn't get auto-handled —
> it pauses and waits for a human, right here. This pause is saved to the
> database, so even if the system restarts, the case is still waiting. I approve
> it... and the agent picks up exactly where it left off. The AI proposes;
> a human stays in control of the expensive calls."

## 4:30 – 5:00 · The numbers + honest close
**Screen:** dashboard strategy table.

> "That was live. Across 300 payments: doing nothing recovers zero. Blind
> retrying gets ₹4.65 lakh but hammers the gateway 770 times. My system recovers
> ₹15.37 lakh — 3.3 times as much — with less than half the attempts.
>
> Honest note: recovery is near the theoretical best because the test set is
> solvable; the real win is efficiency, and it keeps improving as it learns.
>
> So — a decision problem, not a retry problem, with a human on the expensive
> calls and every step on the record. Thank you."

═══════════════════════════════════════════════════════════════════

## Record in two blocks
- **Block 1 (safe, do first):** Part A + the 4:30–5:00 numbers. No live state,
  can't break.
- **Block 2 (live):** 1:00 – 4:30 as one continuous take. If it fumbles, you
  re-shoot only this block.

## If the tunnel dies
Skip the Razorpay-screen failure; run `python scripts\webhook_setup.py selftest
--reason card_declined` instead — same case, real link, no tunnel. Say "I'm
sending the failure webhook locally." Everything else is identical.

## Legibility
1920×1080 · Chrome zoom 125–150% · terminal font 18+ · move the mouse slowly ·
pause 2s after each click.
