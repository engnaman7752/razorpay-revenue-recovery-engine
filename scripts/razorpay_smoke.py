"""Proof that this project really talks to Razorpay — run on your own machine.

Does three things against the REAL Razorpay test API:
  1. authenticates with your test keys
  2. creates an order   (what retry_now does in live mode)
  3. creates a payment link (what payment_link does in live mode)

and prints the real https://rzp.io/... URL you can open in a browser.

    cd D:\\Hackathon\\razorpay-recovery
    python scripts\\razorpay_smoke.py

Reads keys from .env. Test mode only — no real money moves.
"""

import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("httpx missing — activate the venv, or: pip install httpx")

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.razorpay.com/v1"


def load_env():
    env_file = ROOT / ".env"
    if not env_file.exists():
        sys.exit(f"No .env at {env_file}\n  fix: copy env.local.txt .env")
    values = {}
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    key_id = values.get("RAZORPAY_KEY_ID", "")
    key_secret = values.get("RAZORPAY_KEY_SECRET", "")
    if not key_id or not key_secret:
        sys.exit("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET missing from .env")
    if not key_id.startswith("rzp_test_"):
        print(f"WARNING: {key_id} is not a test key — stopping to be safe.")
        sys.exit(1)
    return key_id, key_secret


def main():
    key_id, key_secret = load_env()
    auth = (key_id, key_secret)
    print(f"\nRazorpay test mode — key {key_id}\n" + "=" * 58)

    with httpx.Client(base_url=BASE, auth=auth, timeout=20) as client:
        # 1 — auth check
        print("\n[1/3] authenticating…")
        r = client.get("/payments", params={"count": 1})
        if r.status_code == 401:
            sys.exit("  FAILED: key id/secret rejected.\n"
                     "  Regenerate the pair in Dashboard → API Keys (Test Mode).")
        r.raise_for_status()
        print(f"  OK — API reachable, account has "
              f"{r.json().get('count', 0)} recent test payment(s)")

        # 2 — order (this is exactly what retry_now does in live mode)
        print("\n[2/3] creating an order (what retry_now does)…")
        order = client.post("/orders", json={
            "amount": 249900,                       # ₹2,499
            "currency": "INR",
            "receipt": f"recovery-demo-{int(time.time())}",
            "notes": {"source": "revenue-recovery-engine", "kind": "retry_now"},
        })
        order.raise_for_status()
        print(f"  OK — order {order.json()['id']} for ₹2,499")

        # 3 — payment link (what the agent picks for a hard decline)
        print("\n[3/3] creating a payment link (what payment_link does)…")
        link = client.post("/payment_links", json={
            "amount": 249900,
            "currency": "INR",
            "description": "Complete your failed payment",
            "reference_id": f"recovery-demo-{int(time.time())}",
            "customer": {"name": "Demo Customer", "email": "demo@example.com",
                         "contact": "+919876543210"},
            "notify": {"sms": False, "email": False},   # don't spam anyone
        })
        link.raise_for_status()
        body = link.json()

    print(f"  OK — link {body['id']}")
    print("\n" + "=" * 58)
    print("REAL RAZORPAY PAYMENT LINK — open this in a browser:\n")
    print(f"    {body['short_url']}\n")
    print("This is the exact call LiveRazorpayGateway makes when the agent")
    print("decides 'payment_link'. Pay it with a Razorpay test card and, with")
    print("the webhook configured, the case flips to RECOVERED on its own.")
    print("=" * 58 + "\n")


if __name__ == "__main__":
    main()
