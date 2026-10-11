# Recording day — the whole thing, in order

One page. Follow it top to bottom. Budget 90 minutes including retakes.

The script (what to *say*) is `docs\pitch-script.md`. This file is what to
*do* — the setup, the screen, the clicks.

---

## Part 1 · Pre-flight (20 min, do this first)

### 1.1 Set the config for recording

Open `.env` and confirm these four lines:

```
SERVER_PORT=8081
GATEWAY_MODE=live          <- real Razorpay links get created
GEMINI_MODEL=gemini-3.6-flash
LLM_ENABLED=true           <- or just delete the line
```

`GATEWAY_MODE=live` matters: it's what makes the agent produce a real
`https://rzp.io/...` link on camera. **You do NOT need ngrok for the video** —
see Part 3.

### 1.2 Start everything

VS Code → **Ctrl+Shift+P → Tasks: Run Task → ▶ START EVERYTHING**

Three terminal tabs come up. Wait for all three:

| Terminal | Wait for |
|---|---|
| 1 · Backend | `Tomcat started on port(s): 8081` |
| 2 · Agent | `Uvicorn running on http://127.0.0.1:8000` |
| 3 · Dashboard | `[vite] proxying /api -> http://localhost:8081` |

That third line must say **8081**. If it says 8080, the dashboard will show a
500 and you'll waste ten minutes.

### 1.3 Verify, don't assume

```powershell
python scripts\webhook_setup.py check
```

Every line must be OK except the ngrok warning, which you can ignore.

### 1.4 Stage the approval

```powershell
python scripts\setup_demo.py
```

The batch auto-approved everything, so the Approvals tab is empty until you run
this. It prints a case id — **write it down**, you need it at 3:00.

### 1.5 Prepare the Razorpay moment

```powershell
python scripts\webhook_setup.py selftest --reason card_declined --amount 18000
```

This opens a real LIVE case and the agent answers it with a real Razorpay
payment link. **Write down the case id and the rzp.io URL.** Leave the case
open — you'll recover it on camera.

Open the rzp.io link in a browser tab now and leave that tab parked. You want
it to have finished loading before you're recording.

---

## Part 2 · The screen (10 min)

You are recording **1920x1080**. Set that first, in your recorder, before you
arrange anything.

### Windows you need, in this order

1. **Chrome, one window, three tabs** — nothing else, no bookmarks bar
   - Tab 1: `http://localhost:5173` (Dashboard)
   - Tab 2: the case detail page from 1.5
   - Tab 3: the parked rzp.io payment link
2. **VS Code** — you'll show two files. Open them as tabs now so you're not
   hunting during the take:
   - `agent\policy.yaml`
   - `backend\src\main\java\com\recovery\webhook\RazorpayWebhookController.java`
3. **One PowerShell terminal**, large font, for the two commands you run live

### Make it legible

Judges watch this small, sometimes on a phone.

- Chrome: **Ctrl+ +** twice (125–150% zoom)
- VS Code: **Ctrl+Shift+P → "Editor Font Zoom In"** three times
- Terminal: font size 18+
- Close every other app. Turn off notifications. Airplane-mode your phone.
- Dark mode reads better on compressed video — the dashboard already has it.

### Do a 20-second throwaway take

Record 20 seconds, watch it back, check: is the smallest text readable? Is your
mic level right? Fix it now, not after take four.

---

## Part 3 · The Razorpay segment — do this without ngrok

This is the part everyone gets wrong. **You do not need a tunnel for the
video.** `webhook_setup.py` signs webhooks with your own secret and posts them
at your own backend — byte-for-byte what Razorpay sends. So on camera you get
the entire loop with zero network risk:

1. The case from 1.5 is open, with a **real** Razorpay link the agent created
2. Show the rzp.io tab — that page is genuinely Razorpay's
3. Back in the terminal, run:

   ```powershell
   python scripts\webhook_setup.py pay <case-id-from-1.5>
   ```

4. Refresh the dashboard — the case is **RECOVERED**

**Say this while it happens** (honesty is the point, and it's stronger anyway):

> "The link is real — that page is Razorpay's, created by the agent through
> their API. I'm firing the paid-webhook locally so this doesn't depend on
> conference wifi, but it's the same signed payload Razorpay sends, verified
> with HMAC over the raw request body. Notice the agent's action returned
> *pending*, not *recovered* — creating a link doesn't recover money. Only the
> webhook can close the case."

That replaces Version A / Version B at 4:00 in the script. It's more convincing
than Version B and far less fragile than Version A.

> If you *do* have ngrok working and time to spare, record the real version as
> a bonus take. But record this one first, so you have something in the can.

---

## Part 4 · The take (5 minutes)

Follow `docs\pitch-script.md`. The screen for each beat:

| Time | Screen | Your action |
|---|---|---|
| 0:00 | Dashboard, top | Nothing — just talk |
| 0:50 | Dashboard, strategy table | Point at NAIVE vs AGENT |
| 1:45 | Case detail (tab 2) | Scroll the decision timeline slowly |
| 3:00 | Approvals tab | Approve the case from 1.4, watch it resume |
| 4:00 | rzp.io tab, then terminal | Part 3 above |
| 4:35 | Dashboard | Close on the numbers |

**Two rules that save takes:**

Move the mouse **slowly and deliberately**. Fast cursor movement is the single
biggest thing that makes a screen recording look amateur.

Pause 2 seconds after each click before you speak again. It gives the editor
(and the viewer) room, and it stops you talking over your own UI.

---

## Part 5 · If something breaks mid-take

| Breaks | Do this, keep talking |
|---|---|
| Dashboard 500s | Check terminal 1 is still alive; `Retry` button |
| Agent stops responding | Restart task 2; cases already in the DB still display |
| Gemini 404s / rate-limits | **Don't restart anything.** The timeline says `fallback_error` and the agent still decides correctly — say so on camera, it's your best resilience line |
| Razorpay API refuses | Skip to the code walkthrough (Version B in the script) |
| Everything is on fire | You have `python scripts\prove.py batch` — 42 seconds, no network, computes the whole comparison live |

---

## Part 6 · Before you submit

- [ ] Watch the whole thing once, muted — does the screen alone tell the story?
- [ ] Watch it once with your eyes closed — does the audio alone make sense?
- [ ] Is any real secret visible? Scrub through for `.env` on screen, terminal
      scrollback with keys, the Razorpay dashboard showing your key id
- [ ] Under the time limit
- [ ] Uploaded, link tested in an incognito window

The last one is not a joke. Test the link logged out.
