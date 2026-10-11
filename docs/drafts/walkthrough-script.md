# Detailed walkthrough — chapter by chapter

The long version: setup, architecture, thinking, and the demo. ~13 minutes.

**Record one chapter at a time.** A fumble costs you 90 seconds, not 13
minutes. Stitch them afterwards. Each chapter below says what's on screen,
roughly what to say, and how long it should run.

> If the submission has a hard time limit, `docs\pitch-script.md` is the 5-minute
> cut. Chapters 1, 5, 6 and 8 here are the ones that survive a trim.

---

## Chapter 0 · What you're about to see (0:30)

**Screen:** VS Code with the three terminals running, dashboard in the browser.

> "This is an AI revenue recovery engine for Razorpay's Track 3. Three
> services: a Spring Boot backend, a LangGraph decision agent in Python, and a
> React dashboard. Everything you'll see is running on this laptop right now —
> nothing is pre-recorded and no number on screen is hardcoded."

Pan across the three terminals so people can see them alive.

---

## Chapter 1 · The problem (1:00)

**Screen:** dashboard, top of the page.

> "When a payment fails, most merchants do one of two things: nothing, or retry
> it on a cron job until it works or the customer gets annoyed.
>
> Both are wrong, and for the same reason — they treat every failure as the same
> event. But 'your card is expired' and 'the gateway timed out' are not the same
> problem. One needs a new payment method. The other just needs to be tried
> again in ten seconds. Retrying an expired card three times doesn't recover
> anything; it burns processor fees and trains the customer to ignore you.
>
> So the interesting question isn't 'how do I retry harder'. It's: **given
> what I know about why this specific payment failed, what is the single best
> next action — and is it even worth taking one?**"

---

## Chapter 2 · How I thought about it (1:30)

**Screen:** `agent\graph\ev.py`, scrolled to `PRIORS`.

> "Once you phrase it that way, it stops being a retry problem and becomes a
> decision problem under uncertainty. And that has a standard shape: expected
> value.
>
> For every combination of *cause* and *action*, there's a probability it
> recovers the money. Multiply by the amount at stake, subtract what the action
> costs you — a retry costs processor fees, a text message costs goodwill — and
> you get a number. Rank by that number, take the top one, and if the best
> option is still worth less than doing nothing, do nothing and say so.
>
> That's the whole idea. Everything else in this project is infrastructure
> around that one sentence."

Scroll the priors table.

> "These are the starting probabilities. Soft decline plus a scheduled retry:
> fifty-five percent. Soft decline plus an immediate retry: fifteen — because
> the balance hasn't changed in two seconds. Hard decline plus a retry: two
> percent, basically never. They start as priors and the system learns from
> there — I'll show that."

---

## Chapter 3 · The architecture (2:00)

**Screen:** VS Code file tree, collapsed to top level.

> "Three services, and the split between them is deliberate."

Expand `agent/`:

> "The agent is a LangGraph state machine: diagnose, decide, guard, execute,
> check outcome. It decides. It holds no database connection and it cannot move
> money."

Expand `backend/`:

> "The backend owns every tool that touches the world — the gateway, the
> database, the audit log. The agent asks it to do things over an authenticated
> endpoint. That separation is the point: **the thing that reasons and the thing
> that acts are different processes, and the acting one enforces the rules.**
> An agent that can't be trusted still can't do damage, because the permission
> boundary isn't in the prompt, it's in the network."

Open `agent\graph\build.py`:

> "Here's the graph. Note `guard` sits between `decide` and `execute` — nothing
> reaches the gateway without passing policy. And note the interrupt before
> `human_review`: that's a real pause, checkpointed into Postgres, so an
> approval can wait overnight and survive a restart."

---

## Chapter 4 · The simulation — and being precise about it (2:00)

**Screen:** `docs\simulation.md`, then `data\cases.jsonl`.

This chapter is where honesty earns you marks. Be exact.

> "To measure whether any of this works, I needed a world I could replay. So
> there's a generator that produces 300 synthetic failed payments with a fixed
> seed — same 300 every time, on any machine."

Show one line of `cases.jsonl`, point at `ground_truth`:

> "Each case has a hidden answer key: which single action, if any, would have
> recovered it. Some cases are unrecoverable and the key is null.
>
> The simulator has exactly one rule: an action succeeds if and only if it
> matches that key. No randomness at execution time, so the numbers are
> identical on every run. **The agent never sees the key** — it only learns
> what the gateway returns, success or failure, exactly like production."

> "I want to be precise about a word here. This is a **deterministic replay**,
> not a real-time simulation. That's a deliberate choice: I'm comparing four
> strategies, and the comparison is only fair if all four face an identical
> world. Randomness would mean I'm measuring luck.
>
> The real-time path exists and I'll show it in chapter 8 — the same graph
> against Razorpay's live API, where outcomes arrive asynchronously by webhook.
> But the *benchmark* is deliberately offline, and that's a feature, not a
> shortcut."

Show the four-strategy table in `docs\simulation.md`:

> "Four strategies over that same world. Do-nothing is the floor — what a
> merchant loses today. Naive is three retries on everything, what a cron job
> does. The agent is the system under test. And the oracle reads the answer key
> and plays the one right move — the ceiling nobody can beat."

---

## Chapter 5 · Watch one case get decided (2:30) — THE MONEY SHOT

**Screen:** dashboard → Cases → open one → the decision timeline.

Scroll slowly. Narrate what's actually on screen.

> "Every row here is an audited decision. This is not a log I wrote for the
> demo — it's the `decision_log` table, and the agent physically cannot act
> without writing to it.
>
> Diagnose: the error reason maps to a cause. That's a dictionary lookup, not
> a model — I'm not going to let an LLM hallucinate the diagnosis when the
> mapping is deterministic.
>
> Decide: here's the expected-value ranking the agent saw — every candidate,
> its probability, its EV. It picked the top one.
>
> Guard: policy check. Then execute, then check the outcome."

Find a blocked row:

> "And here's the interesting one. The agent chose an action, and the guard
> **vetoed it**. Contact cap. So it went back and re-decided with that option
> struck off. Both the choice and the block are in the record — you can see the
> agent wanting to do something it wasn't allowed to do, and being stopped."

If the timeline says `fallback_error`, use it:

> "See this? The LLM call failed here. The agent fell back to the deterministic
> ranking and still made the right call, and it logged honestly that it had
> fallen back. The model is a ranker, not the decision-maker — which is why
> this system keeps working on a day when the model API is down."

---

## Chapter 6 · Governance is code, not prompts (1:30)

**Screen:** `agent\policy.yaml`.

> "Every rule the agent obeys lives in this file. Attempt caps, contact caps,
> quiet hours, opt-out, and the twenty-five-thousand-rupee approval line.
>
> None of this is in a prompt. You can't talk the agent out of it, because the
> agent isn't the one enforcing it — the backend is."

Edit a value live (change the approval threshold), save:

> "I can change policy without touching a line of code."

**Screen:** Approvals tab. Approve the staged case.

> "Anything above the line pauses and waits for a human. That pause is a
> LangGraph interrupt checkpointed into Postgres — I can kill the agent
> process, restart it, and the case is still sitting here waiting. When I
> approve it, the graph resumes from exactly where it stopped."

Approve it on camera and let it finish.

---

## Chapter 7 · It learns (1:00)

**Screen:** dashboard learning curve, or the table in `eval\results.md`.

> "Every outcome updates a Beta distribution for that cause-action pair. The
> backend ships the current counts to the agent on every decision, so the
> probabilities drift toward the truth as it works through cases.
>
> Here's what that looks like: contacts per ten thousand rupees recovered, across
> the three hundreds of the run — 1.93, then 1.64, then 1.45. Recovery stays
> flat; **cost drops twenty-five percent.**
>
> That's the honest shape of the improvement. It isn't recovering more, it's
> learning which actions never work and to stop paying for them."

---

## Chapter 8 · It's really Razorpay (1:30)

**Screen:** the live case from `dryrun.py`, then the rzp.io tab, then terminal.

> "Everything so far ran against the simulator. Here's the live path.
>
> This case was opened by a real webhook — a `payment.failed` event, signature
> verified with HMAC over the raw request body. Not the parsed JSON, the raw
> bytes, because re-serializing changes the digest and that's the bug everyone
> ships. There's a unit test for it."

Open the rzp.io tab:

> "The agent's chosen action was a payment link, and this is it. That's
> Razorpay's page, created by the agent through their API."

Back to the terminal:

```powershell
python scripts\webhook_setup.py pay <case-id>
```

> "I'm firing the paid-webhook locally so this doesn't depend on conference
> wifi — but it's the same signed payload Razorpay sends, through the same
> verification.
>
> And notice: when the agent created that link, the outcome was **pending**,
> not recovered. Creating a payment link doesn't recover money. Only the
> webhook can close the case. Most systems count the optimistic outcome. This
> one doesn't."

Refresh the dashboard — RECOVERED.

---

## Chapter 9 · The numbers, and what they do and don't mean (1:30)

**Screen:** dashboard strategy table.

> "Three hundred cases, twenty-three and a half lakh at risk.
>
> Do nothing recovers zero. Naive retrying recovers four point six five lakh
> across seven hundred and seventy payment attempts. The agent recovers
> **fifteen point three seven lakh** using **three hundred and sixteen**
> attempts. Three point three times the money, with less than half the attempts.
> The oracle — perfect play — gets fifteen point four one. The agent lands at
> ninety-nine point seven percent of it."

Then, unprompted, the caveat:

> "I want to say what that ninety-nine point seven actually means. The
> simulator has one right answer per case, and the agent gets four decide loops
> — so recovery is close to exhaustible. The number I'd actually defend is the
> cost side: the agent spends about five times the oracle's contacts, and that
> gap is what the learning system is closing.
>
> If I'd only shown you the recovery number, I'd be overselling it."

---

## Chapter 10 · Close (0:30)

**Screen:** dashboard.

> "So: a decision problem, not a retry problem. Expected value picks the
> action, policy-as-code constrains it, a human approves anything expensive, and
> every single decision is on the record — including the ones that got blocked,
> and including the times the model failed and it fell back.
>
> Three point three times the recovery, at half the attempts. Thank you."

---

## Recording notes

- **One chapter per take.** Number your files `ch01.mp4`, `ch02.mp4`…
- Leave 2 seconds of silence at the start and end of each — makes stitching painless.
- Chapters 2, 3, 4, 6 are code/docs on screen. Zoom VS Code up 3–4 steps.
- Chapters 5, 8, 9 are the dashboard. Chrome at 125–150%.
- If a chapter needs three takes, move on and come back. Don't burn the night on one.
