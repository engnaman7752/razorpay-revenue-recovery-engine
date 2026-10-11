# The no-code demo — just show it working (≈4 min)

No VS Code. No file names. No architecture tour. You only ever show two things:
Razorpay's screen, and your dashboard. Everything is explained in plain words.

Tabs open: Razorpay test dashboard · your dashboard (localhost:5173).

---

## 1 · The problem (30s) — your dashboard, top

> "When an online payment fails, most businesses do one of two things: nothing,
> or blindly retry it until it works or the customer gives up. Both waste money,
> because they treat every failure the same. But 'card expired' and 'network
> glitch' are totally different problems. My system figures out *why* a payment
> failed and picks the single smartest next step — or decides it's not worth
> chasing at all."

---

## 2 · A real failed payment (45s) — Razorpay screen

Create a test payment link, open it, pay with UPI **`failure@razorpay`**.

> "This is Razorpay test mode. I'll fail a payment on purpose... and there it
> is — a real failed transaction. My system just caught it automatically."

---

## 3 · Watch it decide (60s) — your dashboard, open the new case

Scroll the timeline slowly. Explain in plain words, not code terms:

> "Here's what my system did, step by step, on its own.
>
> First it worked out *why* it failed. Then it looked at every possible action —
> retry now, retry later, send a fresh payment link, send a reminder — and
> scored each one by how likely it is to recover the money versus what it costs.
> It picked the best one. Then it checked its own rulebook before doing anything.
> And then it acted — it sent the customer a real Razorpay payment link.
>
> And every single step is written down here. Nothing it does is hidden."

---

## 4 · Recover it (30s)

Pay the link with **`success@razorpay`** — or run the recover command.

> "The customer pays the new link... and the case closes itself as recovered.
> Notice it only counts as recovered once the money actually arrives — not when
> it sent the link. It never counts money it hasn't got."

---

## 5 · The scale + the honest bit (60s) — dashboard numbers

> "That was one payment. Across 300, doing nothing recovers zero. Blind retrying
> recovers ₹4.65 lakh but hammers the gateway 770 times. My system recovers
> **₹15.37 lakh — 3.3 times as much — with less than half the attempts.**
>
> Honest note: it's near the theoretical best on recovery because the test set
> is solvable. The real win is efficiency — it wastes far fewer customer
> contacts, and it keeps getting better as it learns which actions never work.
>
> It also asks a human before anything above ₹25,000, and it works even if the
> AI model is down. Thank you."

---

## What you're NOT saying (and don't need to)
- No file names, no "LangGraph", no "Spring Boot", no code on screen
- The ideas are still all there, just in business words:
  - "figures out why it failed" = the diagnosis
  - "scores each action" = the expected-value engine
  - "checks its rulebook" = policy / guardrails
  - "asks a human above ₹25k" = human-in-the-loop
  - "only counts money that arrived" = pending vs recovered
  - "works even if the AI is down" = the fallback

## If a judge asks a technical question later
Then you open the code. `docs/live-demo-flow.md` has the with-code version ready.
Keep it in your back pocket — you don't lead with it, but you're not caught out.
