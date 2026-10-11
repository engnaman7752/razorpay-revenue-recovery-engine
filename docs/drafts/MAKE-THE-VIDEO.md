# Make the video — the one guide

Read this top to bottom once. It does three things, in order:

1. **Start the project** (5 min)
2. **Understand the whole solution** — one payment walked through every file,
   so you can explain it, not just read a script
3. **Record** — which script, which screen, in what order

The talking scripts are `docs\pitch-script.md` (5-min cut) and
`docs\walkthrough-script.md` (13-min chapters). This file is the map that makes
them make sense.

---

# PART 1 — Start the project (5 minutes)

### Step 1. Open the folder in VS Code
`D:\Hackathon\razorpay-recovery`

### Step 2. Start all three services
**Ctrl+Shift+P → Tasks: Run Task → ▶ START EVERYTHING**

Wait for three terminal tabs to settle:

| Tab | Wait for this exact line |
|---|---|
| 1 · Backend | `Tomcat started on port(s): 8081` |
| 2 · Agent | `Uvicorn running on http://127.0.0.1:8000` |
| 3 · Dashboard | `[vite] proxying /api -> http://localhost:8081` |

If tab 3 says 8080, stop — that's the bug that shows a blank dashboard. It
reads the port from `.env`; make sure `SERVER_PORT=8081` is there.

### Step 3. One command to check everything and stage your demo
**Ctrl+Shift+P → Tasks: Run Task → ✔ DRY RUN**
(or `python scripts\dryrun.py`)

It verifies every service, prints your numbers, and hands you two ready cases:
one waiting for approval, one carrying a real Razorpay link. Keep its final
block on screen while you record — it has your case IDs and the `pay` command.

When the dry run says **"Everything is ready"**, you're set. Now understand
what you're about to show.

---

# PART 2 — How the whole solution works

Don't memorise the code. Follow **one failed payment** through the system once.
Every file it touches, in the order it touches them. After this, the diagram
in your head *is* the pitch.

The whole system answers one question:

> A payment just failed. What is the single best next action — and is it even
> worth taking one?

Here's how a payment travels through it.

---

### ① A payment fails → a case is born

Two ways a case enters the system.

**Simulated (the benchmark):** `data\generate.py` created 300 fake failed
payments with seed 42. `data\cases.jsonl` is that file. Open it, look at one
line — note `ground_truth`, the hidden answer key naming the one action that
would recover it. The agent never sees this.

**Live (real Razorpay):** a real failed payment fires a webhook into
`backend\...\webhook\RazorpayWebhookController.java`. Before anything else,
`SignatureVerifier.java` checks the HMAC signature over the **raw bytes**. Bad
signature → 401, done. Good → a `RecoveryCase` row is created and handed to the
agent.

> **Say in the video:** "A case is just a failed payment plus what we know about
> the customer. It arrives either from the simulator, for the benchmark, or from
> a real signed Razorpay webhook."

---

### ② The backend calls the agent

`backend\...\agent\AgentClient.java` sends the case over HTTP to the Python
agent's `/decide` endpoint (`agent\main.py`).

**This is the most important design decision in the project.** The agent — the
thing that *reasons* — runs in a separate process and holds no database, no
gateway, no ability to move money. It can only decide and ask. The backend is
the only thing that *acts*.

> **Say in the video:** "The brain and the hands are different processes. Even
> if the agent went haywire, it can't do damage — the permission boundary isn't
> in a prompt, it's the network between two services."

---

### ③ The agent decides — the LangGraph loop

Open `agent\graph\build.py`. This is the whole decision flow as a graph:

```
diagnose → decide → guard → execute → check_outcome
                ↑_______________________|   (retry with failed action removed)
```

Walk each node — they're all in `agent\graph\nodes.py`:

**diagnose** — maps the error reason to a cause. `insufficient_fund` →
`SOFT_DECLINE`. It's a dictionary in `agent\graph\ev.py`, not an LLM — you don't
let a model guess a fact you already know.

**decide** — the heart. Ranks every action by **expected value**:
`P(recovery | cause, action) × amount − cost`. The probabilities live in
`ev.py` as `PRIORS`. An LLM (`agent\graph\llm.py`) picks among the top-EV
options, but if the model is down it falls back to pure EV — and logs that it
did. If the best option is worth less than doing nothing, it closes the case
and says so.

**guard** — `agent\graph\guardrails.py` reads `agent\policy.yaml`: attempt
caps, contact caps, quiet hours, opt-out, the ₹25,000 approval line. A veto
sends it back to decide with that action struck off. This sits *between* decide
and execute — nothing reaches the world unchecked.

**execute** — calls back to the backend's tool endpoints
(`backend\...\tools\ToolController.java` → `RetryPaymentTool`,
`PaymentLinkTool`, `ReminderTool`…). The tool asks the gateway.

**check_outcome** — recovered → close. Failed → back to decide, that action
removed.

> **Say in the video:** "It's not a retry loop. It's diagnose, then rank by
> expected value, then a policy check nothing can skip, then act, then look at
> what happened — and every step is written down."

---

### ④ The gateway — simulated or real

`execute` hits one of two implementations behind the same interface
(`RazorpayGateway.java`):

- `SimulatedGateway.java` — for the benchmark. One rule: an action succeeds if
  and only if it equals `ground_truth.recovers_if`. No randomness → identical
  numbers every run.
- `LiveRazorpayGateway.java` — real Razorpay test API. Creates a real order or
  payment link. Returns **PENDING**, never "recovered" — because creating a
  link doesn't recover money. Only a later webhook can.

`GATEWAY_MODE` in `.env` picks which. **Same graph, both ways** — that's the
whole point.

---

### ⑤ Every decision is written down

Every node writes a row via `backend\...\domain\DecisionLogger.java` into the
`decision_log` table. The agent *cannot* act without logging. That table is
exactly what the dashboard's case timeline renders — so what you show judges
isn't a demo log, it's the real audit trail.

---

### ⑥ It learns

Each outcome updates a Beta(α,β) posterior per (cause, action) in the `ev_stats`
table (`EvStatsService.java`). The backend ships current counts to the agent on
every `/decide`, so the probabilities drift toward truth. It shows up as
**cost falling**, not recovery rising: contacts per ₹10k went 1.93 → 1.64 →
1.45 across the run.

---

### ⑦ Humans stay in control

Anything over ₹25,000 hits `escalate` → the graph **pauses** at a LangGraph
interrupt, checkpointed into Postgres. Kill the agent, restart it — the case is
still waiting. `frontend\src\pages\Escalations.jsx` is the approval queue;
approving calls `/api/escalations/{id}/resolve` and the graph resumes from
exactly where it stopped.

---

### The whole thing in one breath

> "A failed payment becomes a case. The backend hands it to a separate agent
> that can't touch money. The agent diagnoses the cause, ranks actions by
> expected value, passes the winner through a policy gate, and asks the backend
> to act — against a simulator for the benchmark, or real Razorpay in live mode.
> Every decision is logged, the probabilities learn from every outcome, and
> anything expensive waits for a human. Result: 3.3× the recovery of naive
> retrying, at half the attempts."

That paragraph is your intro **and** your outro. If you can say it without
reading, you understand your own project — and judges can tell.

---

# PART 3 — Record

Now that you understand the flow, the scripts are just staging.

### Which script
- **Hard time limit (≤5 min):** `docs\pitch-script.md`
- **Detailed walkthrough:** `docs\walkthrough-script.md` — 10 short chapters,
  record one at a time, stitch after. A fumble costs 90 seconds, not everything.

### Record in this order (not the order they play)

Do the "no live state needed" parts first, while you're fresh and nothing can
break:

1. **Intro + problem + your thinking** — talk over the dashboard and over
   `ev.py`. (Walkthrough ch. 0–2)
2. **Architecture** — the file tour from Part 2 above, in execution order.
   `build.py`, then the backend `tools\` folder. (ch. 3)
3. **The simulation, precisely** — `data\cases.jsonl`, `docs\simulation.md`.
   Say "deterministic replay," never "real-time simulation." (ch. 4)

Then the live parts, using the cases the dry run staged:

4. **One case decided** — Cases → open one → scroll the timeline slowly.
   THE money shot. (ch. 5)
5. **Governance** — edit `policy.yaml` on camera, then approve the staged case
   in the Approvals tab. (ch. 6)
6. **Learning** — the curve / the `eval\results.md` table. (ch. 7)
7. **Real Razorpay** — the rzp.io tab, then
   `python scripts\webhook_setup.py pay <case-id>` → RECOVERED. (ch. 8)
8. **Numbers + honest caveat + close.** (ch. 9–10)

### The three lines that win marks
- "The brain and the hands are different processes." (architecture)
- "It's a deterministic replay, so the four-strategy comparison is fair — not
  a real-time sim." (honesty about the benchmark)
- "If I'd only shown the recovery number, I'd be overselling it — the number I
  defend is the cost side." (honesty about results)

### Legibility (judges may watch on a phone)
- Recorder set to 1920×1080 **before** you arrange windows
- Chrome zoom 125–150%, VS Code font +3 steps, terminal font 18+
- Record a 20-second throwaway, watch it back, fix mic + text size
- Move the mouse slowly. Pause 2s after each click.

### Before you submit
- [ ] No secrets on screen (scrub for `.env`, terminal scrollback, Razorpay key)
- [ ] Under the time limit
- [ ] Link tested in an incognito window
