"""Set up and rehearse the live Razorpay webhook loop — run on your machine.

    python scripts\\webhook_setup.py check          # is everything configured?
    python scripts\\webhook_setup.py url            # what to paste into Razorpay
    python scripts\\webhook_setup.py selftest       # fake a payment.failed, locally
    python scripts\\webhook_setup.py selftest --reason insufficient_fund --amount 4999
    python scripts\\webhook_setup.py pay <case-id>  # fake the payment_link.paid

`selftest` and `pay` sign events with your own RAZORPAY_WEBHOOK_SECRET and POST
them straight at your backend, exactly the way Razorpay would. That means you
can rehearse — and debug — the entire loop without ngrok, without the internet,
and without spending a single test payment. If selftest passes, the only thing
left that can break on demo day is the tunnel.
"""

import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx missing — activate the venv (.venv\\Scripts\\Activate.ps1)")

ROOT = Path(__file__).resolve().parents[1]
AGENT = "http://localhost:8000"

GREEN, RED, YELLOW, DIM, BOLD, OFF = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m")
if os.name == "nt":
    os.system("")  # enable ANSI on Windows terminals


def env():
    f = ROOT / ".env"
    if not f.exists():
        sys.exit(f"{RED}no .env at {f}{OFF} — run: copy env.local.txt .env")
    out = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def backend(e):
    port = os.environ.get("BACKEND_PORT") or e.get("SERVER_PORT") or "8080"
    return f"http://localhost:{port}"


def ok(msg):    print(f"  {GREEN}OK{OFF}    {msg}")
def bad(msg):   print(f"  {RED}FAIL{OFF}  {msg}")
def warn(msg):  print(f"  {YELLOW}WARN{OFF}  {msg}")


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def post_event(url: str, event: dict, secret: str, *, corrupt=False):
    """Serialise once, sign those exact bytes, send those exact bytes.
    (Re-serialising would change the digest — the same trap the Java side
    avoids by hashing the raw request body.)"""
    raw = json.dumps(event, separators=(",", ":")).encode()
    sig = sign(raw, secret)
    if corrupt:
        sig = "0" * 64
    return httpx.post(url, content=raw, timeout=30, headers={
        "Content-Type": "application/json",
        "X-Razorpay-Signature": sig,
    })


# ----------------------------------------------------------------- payloads
# Razorpay error_reason -> what the agent will diagnose it as. Anything not in
# this list maps to UNRECOVERABLE, which the agent correctly refuses to spend
# money on — so a self-test with a made-up reason produces no action at all.
SCENARIOS = {
    "card_declined":            "HARD_DECLINE   -> payment link (a real rzp.io URL)",
    "card_disabled_for_online_payments": "HARD_DECLINE   -> payment link",
    "insufficient_fund":        "SOFT_DECLINE   -> scheduled retry",
    "gateway_technical_error":  "TRANSIENT      -> immediate retry",
    "payment_timed_out":        "TRANSIENT      -> immediate retry",
    "authentication_failed":    "CUSTOMER_ACTION-> reminder with link",
    "payment_cancelled":        "CUSTOMER_ACTION-> reminder with link",
    "card_number_invalid":      "UNRECOVERABLE  -> agent declines to act (correct)",
}


def payment_failed_event(amount_paise: int, reason: str):
    pid = "pay_SELFTEST" + uuid.uuid4().hex[:10]
    return pid, {
        "entity": "event",
        "event": "payment.failed",
        "payload": {"payment": {"entity": {
            "id": pid,
            "entity": "payment",
            "amount": amount_paise,
            "currency": "INR",
            "status": "failed",
            "order_id": "order_SELFTEST" + uuid.uuid4().hex[:8],
            "method": "card",
            "email": "demo.customer@example.com",
            "contact": "+919999999999",
            "error_code": "BAD_REQUEST_ERROR",
            "error_description": "payment processing failed",
            "error_source": "issuer",
            "error_reason": reason,
        }}},
        "created_at": int(time.time()),
    }


def order_paid_event(case_id: str):
    """Settles a retry-order case. LiveRazorpayGateway sets receipt = case id,
    and the webhook recovers on order.paid via that receipt."""
    return {
        "entity": "event",
        "event": "order.paid",
        "payload": {"order": {"entity": {
            "id": "order_SELFTEST" + uuid.uuid4().hex[:8],
            "entity": "order",
            "status": "paid",
            "receipt": case_id,
        }}},
        "created_at": int(time.time()),
    }


def link_paid_event(case_id: str):
    return {
        "entity": "event",
        "event": "payment_link.paid",
        "payload": {"payment_link": {"entity": {
            "id": "plink_SELFTEST" + uuid.uuid4().hex[:8],
            "entity": "payment_link",
            "status": "paid",
            # LiveRazorpayGateway writes "<case id>:<timestamp>"; the webhook
            # takes the part before the colon.
            "reference_id": f"{case_id}:{int(time.time() * 1000)}",
        }}},
        "created_at": int(time.time()),
    }


# ------------------------------------------------------------------ commands
def cmd_check():
    e = env()
    b = backend(e)
    print(f"\n{BOLD}Configuration{OFF}")

    for key in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"):
        v = e.get(key, "")
        if not v:
            bad(f"{key} is empty in .env")
        elif key == "RAZORPAY_KEY_ID" and not v.startswith("rzp_test_"):
            bad(f"{key} = {v} is NOT a test key — stop, do not demo with this")
        else:
            ok(f"{key} set ({v[:12]}… )" if key == "RAZORPAY_KEY_ID" else f"{key} set")

    mode = e.get("GATEWAY_MODE", "simulated")
    if mode == "live":
        ok("GATEWAY_MODE=live — agent actions will hit the real Razorpay API")
    else:
        warn(f"GATEWAY_MODE={mode} — set it to 'live' and restart the backend, "
             "or the agent will use the simulator")

    print(f"\n{BOLD}Services{OFF}")
    for name, url in (("backend", f"{b}/api/health"), ("agent", f"{AGENT}/health")):
        try:
            r = httpx.get(url, timeout=5)
            ok(f"{name} up at {url[:url.rindex('/')]} — {r.text[:80]}")
        except Exception as exc:
            bad(f"{name} unreachable at {url} ({type(exc).__name__})")

    print(f"\n{BOLD}Tunnel{OFF}")
    pub = ngrok_url()
    if pub:
        ok(f"ngrok is running — {pub}")
    else:
        warn("ngrok not detected. Start it in its own terminal:  ngrok http "
             + b.rsplit(":", 1)[1])
    print()


def ngrok_url():
    """ngrok exposes its own local API on 4040."""
    try:
        tunnels = httpx.get("http://127.0.0.1:4040/api/tunnels", timeout=3).json()
    except Exception:
        return None
    for t in tunnels.get("tunnels", []):
        if t.get("public_url", "").startswith("https://"):
            return t["public_url"]
    return None


def cmd_url():
    e = env()
    b = backend(e)
    pub = ngrok_url()
    if not pub:
        port = b.rsplit(":", 1)[1]
        sys.exit(f"{RED}ngrok is not running.{OFF}\n\nStart it in its own "
                 f"terminal and leave it open:\n\n    ngrok http {port}\n\n"
                 "then run this command again.")

    print(f"\n{BOLD}Razorpay Dashboard -> Settings -> Webhooks -> Add New Webhook{OFF}\n")
    print(f"  Webhook URL   {BOLD}{pub}/webhook/razorpay{OFF}")
    print(f"  Secret        {BOLD}{e.get('RAZORPAY_WEBHOOK_SECRET', '(not set!)')}{OFF}")
    print(f"  Active events {BOLD}payment.failed{OFF}, {BOLD}payment_link.paid{OFF}, "
          f"{BOLD}order.paid{OFF}")
    print(f"\n{DIM}The secret must match byte-for-byte or every webhook returns 401.")
    print(f"ngrok's URL changes every restart — re-paste it if you restart ngrok.{OFF}\n")


def cmd_selftest(reason="card_declined", amount_rupees=4999):
    e = env()
    b = backend(e)
    secret = e.get("RAZORPAY_WEBHOOK_SECRET", "")
    if not secret:
        sys.exit(f"{RED}RAZORPAY_WEBHOOK_SECRET is not set in .env{OFF}")
    url = f"{b}/webhook/razorpay"

    if reason not in SCENARIOS:
        print(f"{YELLOW}'{reason}' is not a reason the agent knows.{OFF} "
              "It will diagnose UNRECOVERABLE and correctly do nothing.\n"
              "Pick one of:")
        for k, v in SCENARIOS.items():
            print(f"    {k:<36} {v}")
        print()

    print(f"\n{BOLD}Webhook self-test{OFF} -> {url}")
    print(f"{DIM}scenario: {reason} (₹{amount_rupees:,}) — "
          f"{SCENARIOS.get(reason, 'unknown reason -> UNRECOVERABLE')}{OFF}\n")

    # 1. a forged signature must be rejected
    print("[1/3] sending an event with a BAD signature (must be rejected)…")
    pid, ev = payment_failed_event(amount_rupees * 100, reason)
    try:
        r = post_event(url, ev, secret, corrupt=True)
    except Exception as exc:
        sys.exit(f"  {RED}backend unreachable at {url}{OFF} ({type(exc).__name__}) "
                 f"— is it running?")
    if r.status_code == 401:
        ok("401 — forged signatures are rejected")
    else:
        bad(f"expected 401, got {r.status_code} {r.text[:120]}")
        sys.exit(1)

    # 2. the real thing
    print("\n[2/3] sending a properly signed payment.failed…")
    r = post_event(url, ev, secret)
    if r.status_code != 200:
        bad(f"expected 200, got {r.status_code} {r.text[:200]}")
        sys.exit(1)
    body = r.json()
    case_id = body.get("case_id")
    if not case_id:
        bad(f"no case_id in response: {body}")
        sys.exit(1)
    ok(f"accepted — LIVE case {case_id} opened for {pid}")

    # 3. did the agent actually pick it up?
    print("\n[3/3] waiting for the agent to work the case…")
    detail, timeline = None, []
    for _ in range(30):
        time.sleep(1)
        try:
            detail = httpx.get(f"{b}/api/cases/{case_id}", timeout=10).json()
        except Exception:
            continue
        timeline = detail.get("timeline") or detail.get("decision_log") or []
        last = timeline[-1]["node"] if timeline else None
        if last in ("close", "human_review", "escalate_notify"):
            break
        if detail.get("status") in ("RECOVERED", "CLOSED", "ESCALATED", "WAITING_APPROVAL"):
            break
    if not detail:
        bad("could not read the case back")
        sys.exit(1)

    status = detail.get("status")
    ok(f"status={status}")

    # the full trail, not just node names — this is where you see WHY
    print(f"\n{BOLD}Timeline{OFF}")
    link = None
    for t in timeline:
        node = (t.get("node") or "?")
        act = t.get("action_chosen") or t.get("action") or ""
        why = (t.get("reasoning") or "").strip().replace("\n", " ")
        out = t.get("outcome") or ""
        flag = f"{RED}BLOCKED{OFF} " if t.get("blocked") else ""
        line = f"  {node:<16} {act:<20} {flag}{why[:88]}"
        if out:
            line += f" {DIM}[{out}]{OFF}"
        print(line)
        if "rzp.io" in why:
            link = why[why.index("https://rzp.io"):].split()[0]

    executed = [t for t in timeline if (t.get("node") or "") == "execute"]
    print()
    if link:
        ok("the agent created a REAL Razorpay artefact:")
        print(f"\n    {BOLD}{link}{OFF}\n")
        print("Open it in a browser. With the webhook registered, paying it with")
        print("the test UPI id  success@razorpay  flips this case to RECOVERED.")
    elif executed:
        ok("the agent executed an action (no payment link in this scenario)")
    else:
        warn("the agent took NO action on this case.")
        print(f"{DIM}  That is usually correct behaviour, not a bug: the diagnosis was")
        print("  low-value enough that every action's expected value fell below the")
        print("  policy threshold, so the guard vetoed and the case was closed.")
        print(f"  For a demo that produces a real payment link, use:{OFF}")
        print(f"\n    python scripts\\webhook_setup.py selftest --reason card_declined\n")

    print(f"{BOLD}Case:{OFF} http://localhost:5173/#/cases/{case_id}")
    if link or executed:
        print(f"{DIM}Rehearse the recovery half without paying anything:{OFF}")
        print(f"    python scripts\\webhook_setup.py pay {case_id}\n")
    else:
        print()


def cmd_pay(case_id: str):
    e = env()
    b = backend(e)
    secret = e.get("RAZORPAY_WEBHOOK_SECRET", "")
    url = f"{b}/webhook/razorpay"
    # A case may be waiting on a payment LINK (payment_link.paid, matched by
    # reference_id) or a retry ORDER (order.paid, matched by receipt). We don't
    # need to know which — fire both; the backend ignores the one that doesn't
    # match, and recover() is idempotent so there's no double-count.
    print(f"\nsettling case {case_id} (sending payment_link.paid + order.paid)…")
    settled = False
    for name, builder in (("payment_link.paid", link_paid_event),
                          ("order.paid", order_paid_event)):
        r = post_event(url, builder(case_id), secret)
        if r.status_code != 200:
            print(f"  {RED}{name}: {r.status_code}{OFF} {r.text[:160]}")
            continue
        body = r.json()
        print(f"  {DIM}{name}: {body}{OFF}")
        if body.get("status") == "RECOVERED":
            settled = True
    detail = httpx.get(f"{b}/api/cases/{case_id}", timeout=10).json()
    status = detail.get("status")
    if status == "RECOVERED":
        ok("case is RECOVERED — the loop closes correctly")
    else:
        bad(f"case status is {status}, expected RECOVERED "
            f"(is GATEWAY_MODE=live and this the right case id?)")
    print()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == "check":
        cmd_check()
    elif cmd == "url":
        cmd_url()
    elif cmd == "selftest":
        args = sys.argv[2:]
        reason, amount = "card_declined", 4999
        while args:
            flag = args.pop(0)
            if flag == "--reason" and args:
                reason = args.pop(0)
            elif flag == "--amount" and args:
                amount = int(args.pop(0))
            else:
                sys.exit(f"unknown option {flag}\n\nreasons:\n" +
                         "\n".join(f"    {k:<36} {v}" for k, v in SCENARIOS.items()))
        cmd_selftest(reason, amount)
    elif cmd == "pay":
        if len(sys.argv) < 3:
            sys.exit("usage: python scripts\\webhook_setup.py pay <case-id>")
        cmd_pay(sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
