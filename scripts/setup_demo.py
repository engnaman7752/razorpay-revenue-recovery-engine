"""Put one high-value case into the approval queue, ready to demo.

The batch runs every case with auto-approval on, so nothing is left waiting for
a human — the Approvals tab ends up empty. This picks a case above ₹25,000,
resets it, and runs it in LIVE mode (no auto-approval) so the graph pauses at
human_review and the case shows up in the queue.

Run this before every demo.

    cd D:\\Hackathon\\razorpay-recovery
    python scripts\\setup_demo.py

Needs: the backend running, the agent on :8000, and .env at the repo root.
Backend port comes from SERVER_PORT in .env (default 8080), same as the dashboard.
"""

import os
import sys
from pathlib import Path

try:
    import httpx
    import psycopg
except ImportError as e:
    sys.exit(f"missing {e.name} — activate the venv first (.venv\\Scripts\\Activate.ps1)")

ROOT = Path(__file__).resolve().parents[1]
AGENT = "http://localhost:8000"


def _backend_url():
    """Same resolution order as frontend/vite.config.js, so the script and the
    dashboard always talk to the same backend."""
    port = os.environ.get("BACKEND_PORT")
    if not port:
        f = ROOT / ".env"
        if f.exists():
            for line in f.read_text().splitlines():
                k, _, v = line.partition("=")
                if k.strip() == "SERVER_PORT" and v.strip().isdigit():
                    port = v.strip()
                    break
    return f"http://localhost:{port or 8080}"


BACKEND = _backend_url()


def env():
    f = ROOT / ".env"
    if not f.exists():
        sys.exit(f"no .env at {f} — run: copy env.local.txt .env")
    out = {}
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def dsn(e):
    if e.get("AGENT_DATABASE_URL"):
        return e["AGENT_DATABASE_URL"]
    url = e.get("DATABASE_URL", "")
    if url.startswith("jdbc:"):
        base = url[len("jdbc:"):]
        scheme, rest = base.split("://", 1)
        return f"{scheme}://{e.get('DATABASE_USER','')}:{e.get('DATABASE_PASSWORD','')}@{rest}"
    return url


def check(name, url):
    try:
        httpx.get(url, timeout=5).raise_for_status()
    except Exception:
        sys.exit(f"{name} is not responding at {url}\n"
                 f"  start it first — see START-HERE.md")
    print(f"  {name} is up")


def main():
    e = env()
    print("\nchecking services…")
    check("backend", f"{BACKEND}/api/health")
    check("agent", f"{AGENT}/health")

    health = httpx.get(f"{AGENT}/health", timeout=5).json()
    if not health.get("durable_checkpoints"):
        print("\n  WARNING: agent has durable_checkpoints=false.")
        print("  Approvals will still work, but the pause will NOT survive an")
        print("  agent restart. Load .env in the agent's terminal to fix:")
        print("    . .\\scripts\\load-env.ps1\n")

    # pick the biggest recoverable, non-opted-out case above the escalation line
    print("\npicking a case above ₹25,000…")
    with psycopg.connect(dsn(e), autocommit=True) as conn:
        row = conn.execute("""
            SELECT id, amount_paise, error_reason
            FROM recovery_case
            WHERE amount_paise > 2500000
              AND COALESCE((customer_history->>'opted_out')::bool, false) = false
              AND COALESCE((ground_truth->>'recoverable')::bool, true) = true
            ORDER BY amount_paise DESC
            LIMIT 1
        """).fetchone()
        if not row:
            sys.exit("no case above ₹25,000 found — has the batch been run?")
        case_id, amount, reason = row
        conn.execute("""
            UPDATE recovery_case
            SET status='DETECTED', attempts=0, contacts_made=0, recovered_paise=0
            WHERE id=%s
        """, (case_id,))
    print(f"  {str(case_id)[:8]}  ₹{amount/100:,.0f}  {reason}")

    print("\nrunning it in live mode (no auto-approval)…")
    r = httpx.post(f"{BACKEND}/api/cases/{case_id}/process", timeout=60)
    r.raise_for_status()
    body = r.json()

    if not body.get("paused"):
        sys.exit(f"expected the case to pause, got status={body.get('status')}\n"
                 f"  full response: {body}")
    print(f"  paused at human_review — status {body['status']}")

    queue = httpx.get(f"{BACKEND}/api/escalations", timeout=10).json()
    ids = [q["case_id"] for q in queue]
    if str(case_id) not in ids:
        sys.exit("case did not appear in /api/escalations")

    print(f"\n{'='*58}")
    print(f"READY — {len(queue)} case(s) waiting for approval")
    print(f"\n  Approvals tab:  http://localhost:5173/#/escalations")
    print(f"  This case:      http://localhost:5173/#/cases/{case_id}")
    print(f"\nDemo it: click Approve and the agent resumes from its checkpoint.")
    print(f"For the strongest version, restart the agent BEFORE approving —")
    print(f"the pause is stored in Postgres and survives it.")
    print(f"{'='*58}\n")


if __name__ == "__main__":
    main()
