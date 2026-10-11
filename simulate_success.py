import hmac
import hashlib
import json
import requests
import sys
from pathlib import Path

# Get Case ID from the command line or from user input
if len(sys.argv) > 1:
    case_id = sys.argv[1].strip()
else:
    case_id = input("Paste the Case ID (UUID from dashboard) to mark as recovered: ").strip()

# Load secret securely from .env
env_file = Path(__file__).parent / ".env"
secret = None
with open(env_file, "r") as f:
    for line in f:
        if line.startswith("RAZORPAY_WEBHOOK_SECRET="):
            secret = line.strip().split("=", 1)[1]
            break

if not secret:
    print("Error: Could not find RAZORPAY_WEBHOOK_SECRET in .env!")
    sys.exit(1)

# Craft the payload simulating a successful Razorpay payment!
# LiveRazorpayGateway sets the 'receipt' field to our internal Case ID when it creates an Order.
payload = {
    "event": "order.paid",
    "payload": {
        "order": {
            "entity": {
                "id": "order_demo_video_123",
                "receipt": case_id
            }
        }
    }
}

body = json.dumps(payload).encode('utf-8')
# Generate Razorpay's HMAC-SHA256 signature
signature = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()

headers = {
    "Content-Type": "application/json",
    "X-Razorpay-Signature": signature
}

print(f"💰 Simulating a successful payment for case {case_id}...")
res = requests.post("http://localhost:8081/webhook/razorpay", data=body, headers=headers)

if res.status_code == 200:
    print("✅ Success! Your dashboard will now show this case as RECOVERED!")
else:
    print(f"❌ Failed: {res.status_code} - {res.text}")
