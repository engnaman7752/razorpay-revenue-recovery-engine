# 5-minute pitch video — shot-by-shot script

Total 5:00. Left column = what is on screen. Right = what you say (written to be
spoken, ~150 wpm). Timings are cumulative.

**Before you hit record**, see the checklist at the bottom.

---

## 0:00 – 0:25 · The problem (25s)

**Screen:** Dashboard, hero number visible. Do not move the mouse.

> "Every Indian merchant on Razorpay loses revenue to payments that simply
> fail. The card was fine, the customer wanted to pay — the bank said no.
>
> Most teams do one of two things: nothing, or a blind cron job that retries
> every failed payment three times. Both leave money on the floor, and the
> second one also annoys customers who were never going to pay anyway.
>
> We built an agent that treats this properly."

---

## 0:25 – 0:50 · The claim (25s)

**Screen:** Stay on the dashboard. Optionally the README architecture diagram.

> "Our claim is that recovery is a portfolio decision problem: which rupees to
> chase, how to chase them, and — the part everyone skips — when to stop.
>
> Three services: a Spring Boot backend that owns the money and the database,
> a Python LangGraph agent that owns decisions and nothing else, and a
> dashboard. The agent cannot call Razorpay. It cannot write to business
> tables. It has exactly six authenticated tools. That constraint is the
> design."

---

## 0:50 – 1:45 · The numbers (55s)

**Screen:** Dashboard. Point at the hero, then the strategy bar chart, then
the learning curve.

> "Three hundred synthetic failed payments, twenty-three lakh rupees at risk,
> run through four strategies against an identical simulator.
>
> Doing nothing recovers zero. Naive retry — three attempts on every case —
> recovers four point six five lakh, and burns seven hundred and seventy
> payment attempts to do it.
>
> Our agent recovers fifteen point three six lakh. That is three point three
> times naive, with less than half the attempts. The oracle — a player that
> cheats and reads the answer key — gets fifteen point four one. We are at
> ninety-nine point seven percent of a perfect player.
>
> And this curve is the part I care about. Recovery stays flat across the
> batch while contacts per ten thousand rupees recovered falls from one point
> nine three to one point four five. The agent is learning to stop wasting
> outreach."

---

## 1:45 – 3:00 · How one case is decided (75s) — THE MONEY SHOT

**Screen:** Cases → click a HARD_DECLINE case with a rich timeline. Scroll the
timeline slowly. Pause on a `decide` entry with the EV ranking bars.

> "Here is a single case, and every decision the agent made on it.
>
> First, diagnose. Razorpay says `card_disabled_for_online_payments`, and a
> dictionary — not the language model — maps that to a hard decline. Root
> cause classification is deterministic, so it is auditable.
>
> Then decide. This block is the expected value ranking the agent actually
> saw: probability of recovery times the amount, minus what the action costs,
> minus a penalty for bothering the customer again. Payment link scores a
> hundred and twenty-two thousand. Retrying scores five thousand — because a
> disabled card does not un-disable itself. The model picks among these
> ranked options; it never invents one.
>
> Then guard, then execute, then check the outcome — and if it failed, we
> loop back to decide with that action struck off. Notice the loop counter and
> the vetoed list growing.
>
> Every row here is a database row. If a judge asks 'why did it do that', the
> answer is on screen, with the inputs it saw."

---

## 3:00 – 4:00 · Governance is code, not prompts (60s)

**Screen:** Scroll to a red BLOCKED entry. Then go to Approvals. Approve one.

> "Now the part that makes this deployable.
>
> This red entry is the guard blocking the agent's own choice. Max decide
> loops exhausted — stop. These limits live in a policy file read by pure
> Python: attempt caps, contact caps, quiet hours in IST, and opt-out as an
> immediate hard stop. Six customers in this batch had opted out; the agent
> took zero actions on all six.
>
> The model is told in its prompt that these rules exist and that it cannot
> bypass them — because it genuinely cannot. They are enforced after it
> answers.
>
> Cases above twenty-five thousand rupees pause here, before any action.
> [click Approve] Approving resumes the agent from a checkpoint stored in
> Postgres. And that pause survives the agent process being killed and
> restarted — which is exactly what happens in production during a deploy."

**Optional 10s if you have time:** restart the agent container before clicking
Approve, so the resume is visibly after a restart.

---

## 4:00 – 4:35 · It is really Razorpay (35s)

Pick ONE of these three. **Version C is the recommended one** — it shows
the full loop with a real Razorpay link and needs no tunnel.

### Version A — you have the live webhook set up

**Screen:** Razorpay test dashboard → trigger a failed payment. Cut to the
dashboard showing the new LIVE case.

> "This is not only a simulation. In live mode the same graph runs against
> Razorpay's test API. A real failed payment fires a webhook — verified with
> HMAC over the raw request body, so a re-serialized payload is rejected — and
> that opens a case, which the agent picks up and answers with a real payment
> link. When the link is paid, the webhook closes the loop."

### Version B — no live setup (equally honest)

**Screen:** `RazorpayWebhookController.java` and `LiveRazorpayGateway.java`.

> "The same graph runs against the real Razorpay test API by flipping one
> environment variable. Webhooks are verified with HMAC over the raw request
> body — we have a unit test proving that a re-serialized but identical JSON
> payload fails, because that is the bug everyone ships. In live mode actions
> return pending rather than recovered, because creating a payment link does
> not recover money — the payment webhook does."

### Version C — the full loop, no tunnel (RECOMMENDED)

Set up in `RECORD-TOMORROW.md` §1.5. You have a live case whose payment link
the agent really created through Razorpay's API.

**Screen:** the `rzp.io` tab (Razorpay's own page), then your terminal, then
the dashboard.

```powershell
python scripts\webhook_setup.py pay <case-id>
```

> "The link is real — that page is Razorpay's, created by the agent through
> their API. I'm firing the paid-webhook locally so this doesn't depend on
> conference wifi, but it's the same signed payload Razorpay sends, verified
> with HMAC over the raw request body. Notice the agent's action returned
> *pending*, not *recovered* — creating a payment link doesn't recover money.
> Only the webhook can close the case."

Refresh the dashboard. RECOVERED.

---

## 4:35 – 5:00 · Close (25s)

**Screen:** Dashboard, or the README limitations section.

> "One honest note. Ninety-nine point seven percent of oracle is high partly
> because our simulator has one right answer per case, which makes the space
> nearly searchable. The number I would actually defend is the cost one: the
> agent spends five times the oracle's customer contacts, and that gap is what
> the learning system closes.
>
> Recovery is a portfolio decision problem, executed under policy-as-code
> governance, with every decision audited. Thank you."

---

## Pre-recording checklist

1. `docker compose up` (or the three services) — all healthy.
2. Batch has been run, so the dashboard is populated.
3. **At least one case left paused** in Approvals — do not approve them all
   while rehearsing.
4. Pick your timeline case in advance and keep the URL in a second tab. Best
   choice: a hard decline with 3+ decide loops and one red blocked entry.
5. Browser at 100% zoom, 1920×1080, dark or light — pick one and stay.
6. Close Slack, notifications, and any tab with a secret in it.
7. `.env` must not be on screen at any point.

## Recording tips

- Record in three takes — numbers, case detail, governance — and cut together.
  Nobody nails five minutes in one pass.
- Move the mouse deliberately. Slow scroll on the timeline; that is the shot
  judges will replay.
- If something breaks mid-take, keep talking and cut later.
- Do not read this script flat. Land these four phrases: *"when to stop"*,
  *"the model picks among ranked options, it never invents one"*, *"they are
  enforced after it answers"*, *"the pause survives a restart"*.

## If a live service dies mid-recording

Fall back to `python frontend/dev-mock-api.py` + `npm run dev` — the full UI
with real agent decisions, no JVM and no database. Nothing in this script
changes except the live-Razorpay section, where you use Version B.
