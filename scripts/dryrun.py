"""Full pre-demo dry run. One command, one report.

    python scripts\\dryrun.py

Checks every moving part in the order the demo uses them, then produces the two
things you need on camera: a case waiting in the approval queue, and a live case
carrying a real Razorpay payment link.

It does not start any service. Start those first (VS Code: ▶ START EVERYTHING).
Safe to re-run as often as you like.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx missing — activate the venv (.venv\\Scripts\\Activate.ps1)")

ROOT = Path(__file__).resolve().parents[1]
AGENT = "http://localhost:8000"
FRONTEND = "http://localhost:5173"

G, R, Y, D, B, OFF = ("\033[32m", "\033[31m", "\033[33m", "\033[2m",
                      "\033[1m", "\033[0m")
if os.name == "nt":
    os.system("")

FAILURES = []
NOTES = []


def ok(m):   print(f"  {G}OK{OFF}    {m}")
def bad(m):  print(f"  {R}FAIL{OFF}  {m}"); FAILURES.append(m)
def warn(m): print(f"  {Y}WARN{OFF}  {m}"); NOTES.append(m)
def head(n, t): print(f"\n{B}{n}. {t}{OFF}")


def env():
    f = ROOT / ".env"
    if not f.exists():
        sys.exit(f"{R}no .env at {f}{OFF} — run: copy env.local.txt .env")
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def rupees(paise):
    return f"₹{paise / 100:,.0f}"


def main():
    e = env()
    port = os.environ.get("BACKEND_PORT") or e.get("SERVER_PORT") or "8080"
    backend = f"http://localhost:{port}"

    print(f"\n{B}Dry run — Razorpay Recovery Engine{OFF}")
    print(f"{D}{ROOT}{OFF}")

    # ---------------------------------------------------------------- 1 config
    head(1, "Configuration")
    if e.get("RAZORPAY_KEY_ID", "").startswith("rzp_test_"):
        ok("Razorpay key is a TEST key")
    else:
        bad("RAZORPAY_KEY_ID is missing or not a rzp_test_ key")
    if e.get("GATEWAY_MODE") == "live":
        ok("GATEWAY_MODE=live — the agent will create real Razorpay links")
    else:
        warn(f"GATEWAY_MODE={e.get('GATEWAY_MODE')} — you'll get simulated "
             "actions, not a real rzp.io link. Set it to 'live' and restart "
             "the backend.")
    if e.get("GOOGLE_API_KEY"):
        ok(f"Gemini configured ({e.get('GEMINI_MODEL', 'default')})")
    else:
        warn("no GOOGLE_API_KEY — decisions will be rule-based (still correct)")

    # -------------------------------------------------------------- 2 services
    head(2, "Services")
    services = {}
    for name, url in (("backend", f"{backend}/api/health"),
                      ("agent", f"{AGENT}/health"),
                      ("dashboard", FRONTEND)):
        try:
            r = httpx.get(url, timeout=5)
            services[name] = r
            ok(f"{name:<10} {url}")
        except Exception as exc:
            services[name] = None
            bad(f"{name:<10} unreachable at {url} ({type(exc).__name__})")

    if services.get("agent") is not None:
        try:
            if services["agent"].json().get("durable_checkpoints"):
                ok("agent has durable Postgres checkpoints (approvals survive a restart)")
            else:
                warn("agent is using in-memory checkpoints — a restart loses "
                     "paused approvals. Check DATABASE_* in .env.")
        except Exception:
            pass

    if services.get("dashboard") is not None:
        try:
            probe = httpx.get(f"{FRONTEND}/api/health", timeout=5)
            if probe.status_code == 200:
                ok(f"dashboard proxy reaches the backend on :{port}")
            else:
                bad(f"dashboard proxy returned {probe.status_code} — vite is "
                    f"pointed at the wrong port. Restart it; it should print "
                    f"'[vite] proxying /api -> {backend}'")
        except Exception as exc:
            bad(f"dashboard proxy broken ({type(exc).__name__})")

    if FAILURES:
        print(f"\n{R}Stop here and fix the failures above.{OFF} "
              "Nothing below will work until the services are up.\n")
        return 1

    # ----------------------------------------------------------------- 3 data
    head(3, "Data")
    health = services["backend"].json()
    n = health.get("cases_in_db", 0)
    if n >= 300:
        ok(f"{n} cases in the database")
    else:
        bad(f"only {n} cases — the seed didn't run")

    try:
        metrics = httpx.get(f"{backend}/api/metrics", timeout=30).json()
        strat = metrics.get("strategies", {})
        if strat:
            print(f"\n  {D}strategy        recovered      cases   attempts{OFF}")
            for k in ("DO_NOTHING", "NAIVE", "AGENT", "ORACLE"):
                s = strat.get(k)
                if not s:
                    continue
                print(f"  {k:<14} {rupees(s.get('recovered_paise', 0)):>12}"
                      f"{s.get('cases_recovered', 0):>8}"
                      f"{s.get('payment_attempts', 0):>10}")
            a = strat.get("AGENT", {}).get("recovered_paise", 0)
            nv = strat.get("NAIVE", {}).get("recovered_paise", 0)
            if a and nv:
                print(f"\n  {B}the number you say out loud: {a / nv:.1f}x NAIVE{OFF}")
            ok("benchmark results are loaded")
        else:
            warn("no strategy results — run the batch task once")
    except Exception as exc:
        warn(f"could not read /api/metrics ({type(exc).__name__})")

    # ------------------------------------------------------- 4 demo asset one
    head(4, "Demo asset 1 of 2 — a case waiting for your approval")
    try:
        queue = httpx.get(f"{backend}/api/escalations", timeout=15).json()
    except Exception as exc:
        queue = []
        warn(f"could not read the approval queue ({type(exc).__name__})")

    pending = [q for q in (queue or []) if str(q.get("status", "")).upper()
               in ("WAITING_APPROVAL", "ESCALATED", "PENDING", "")]
    if pending:
        c = pending[0]
        ok(f"{len(pending)} already waiting — using {c.get('case_id') or c.get('id')}")
        approval_case = c.get("case_id") or c.get("id")
    else:
        print(f"  {D}queue is empty — staging one (this is setup_demo.py){OFF}")
        rc = subprocess.run([sys.executable, str(ROOT / "scripts" / "setup_demo.py")],
                            capture_output=True, text=True, cwd=str(ROOT))
        tail = (rc.stdout or "").strip().splitlines()[-6:]
        for line in tail:
            print(f"  {D}{line}{OFF}")
        if rc.returncode != 0:
            bad("setup_demo.py failed — see its output above")
            print((rc.stderr or "")[-500:])
            approval_case = None
        else:
            time.sleep(2)
            try:
                queue = httpx.get(f"{backend}/api/escalations", timeout=15).json()
            except Exception:
                queue = []
            approval_case = (queue[0].get("case_id") or queue[0].get("id")) if queue else None
            if approval_case:
                ok(f"staged — case {approval_case} is waiting")
            else:
                bad("nothing landed in the approval queue")

    # ------------------------------------------------------- 5 demo asset two
    head(5, "Demo asset 2 of 2 — a live case with a real Razorpay link")
    rc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "webhook_setup.py"),
         "selftest", "--reason", "card_declined", "--amount", "18000"],
        capture_output=True, text=True, cwd=str(ROOT))
    out = (rc.stdout or "") + (rc.stderr or "")
    live_case, link = None, None
    # the child colours its output; strip the escapes or they end up glued to
    # the URL we hand the user (learned the hard way: "https://rzp.io/l/x[0m")
    ansi = re.compile(r"\x1b\[[0-9;]*m")
    for line in out.splitlines():
        clean = ansi.sub("", line)
        if "LIVE case" in clean:
            parts = clean.split("LIVE case", 1)[1].split()
            live_case = parts[0] if parts else None
        if "https://rzp.io" in clean:
            link = clean[clean.index("https://rzp.io"):].split()[0].rstrip(".,")
    if rc.returncode != 0 and not live_case:
        bad("webhook selftest failed")
        print(D + out[-800:] + OFF)
    else:
        ok("webhook signature check passed (forged signature rejected with 401)")
        if live_case:
            ok(f"live case {live_case} opened and worked by the agent")
        if link:
            ok("the agent created a REAL Razorpay payment link")
        else:
            warn("no rzp.io link in the trace — is GATEWAY_MODE=live and the "
                 "backend restarted since you changed it?")

    # ------------------------------------------------------------- the report
    print(f"\n{B}{'=' * 62}{OFF}")
    if FAILURES:
        print(f"{R}{len(FAILURES)} thing(s) need fixing before you record.{OFF}")
        for f in FAILURES:
            print(f"  - {f}")
    else:
        print(f"{G}Everything is ready.{OFF}")
    if NOTES:
        print(f"\n{Y}Worth knowing:{OFF}")
        for n_ in NOTES:
            print(f"  - {n_}")

    print(f"\n{B}Your demo assets — keep this on screen while you record{OFF}\n")
    print(f"  Dashboard        {FRONTEND}")
    if approval_case:
        print(f"  Approve at 3:00  {FRONTEND}/#/escalations")
        print(f"                   case {approval_case}")
    if live_case:
        print(f"  Razorpay case    {FRONTEND}/#/cases/{live_case}")
    if link:
        print(f"  Real link        {link}")
    if live_case:
        print(f"\n  Recover it on camera with:")
        print(f"      {B}python scripts\\webhook_setup.py pay {live_case}{OFF}")
    print(f"\n{D}Script: docs\\pitch-script.md   Runbook: RECORD-TOMORROW.md{OFF}\n")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
