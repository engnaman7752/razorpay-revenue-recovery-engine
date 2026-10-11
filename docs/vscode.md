# Running everything from VS Code

Easier than juggling PowerShell windows: every service gets its own terminal
tab inside the editor, and you start them from a menu.

## One-time

1. **File → Open Folder** → `D:\Hackathon\razorpay-recovery`
   (open the whole repo, not a subfolder — the tasks use the workspace root)
2. Install the recommended extensions when VS Code offers them
   (Python, Extension Pack for Java, Tailwind).
3. If you have no `.venv` yet: **Ctrl+Shift+P → Tasks: Run Task →
   `Setup · create venv + install deps`**

## Starting the services

**Ctrl+Shift+P** → type `run task` → **Tasks: Run Task** → pick:

| Task | What it does |
|---|---|
| **▶ START EVERYTHING** | backend + agent + dashboard, each in its own tab |
| 1 · Backend (port 8080) | just the backend |
| 2 · Agent (port 8000) | just the agent |
| 3 · Dashboard (port 5173) | just the frontend |

Each opens a dedicated terminal tab at the bottom. Switch between them with
the dropdown on the right of the terminal panel. To stop one, click its tab
and press Ctrl+C.

No venv activation needed — the tasks call `.venv\Scripts\python.exe`
directly, and both services read `.env` by themselves.

## Demo tasks

| Task | When |
|---|---|
| **Demo · stage an approval** | before every demo — puts a case in the queue |
| **Demo · prove ONE case** | the 5-second side-by-side comparison |
| **Demo · prove ALL 300 live** | the 45-second full run |
| **Demo · check Razorpay keys** | prints a real payment link |
| Run the 300-case batch | re-seed the dashboard (needs 1 and 2 running) |
| Tests · agent (45) | the whole Python suite |

## Debugging

**Run and Debug** panel (Ctrl+Shift+D) has two configurations:

- **Debug the agent** — set a breakpoint in `agent/graph/nodes.py` inside
  `decide` or `guard`, then process a case. Excellent for explaining the
  decision flow to someone.
- **Debug the backend** — needs the Java extension pack.

## Checking a service is alive

Open a new terminal (Ctrl+Shift+`) and:

```powershell
curl http://localhost:8080/api/health     # backend
curl http://localhost:8000/health         # agent
```

`Unable to connect to the remote server` means that service is not running —
look at its terminal tab for the error.
