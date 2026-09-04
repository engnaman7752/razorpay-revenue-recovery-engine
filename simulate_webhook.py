import hmac
import hashlib
import json
import requests
import time

import os
from pathlib import Path

# Load secret from .env securely
env_file = Path(__file__).parent / ".env"
with open(env_file, "r") as f:
    for line in f:
        if line.startswith("RAZORPAY_WEBHOOK_SECRET="):
            secret = line.strip().split("=", 1)[1]
            break

payload = {
    "event": "payment.failed",
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_demo_" + str(int(time.time())),
                "amount": 2800000, # ₹28,000.00 (Triggers Human Approval > ₹25,000 threshold)
                "currency": "INR",
                "error_reason": "insufficient_fund",
                "error_source": "customer",
                "email": "judge@razorpay.com"
            }
        }
    }
}

body = json.dumps(payload).encode('utf-8')
# Generate Razorpay's HMAC-SHA256 signature to pass the Security Verifier
signature = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()

headers = {
    "Content-Type": "application/json",
    "X-Razorpay-Signature": signature
}

print("💳 Simulating a live payment failure from Razorpay...")
print("Amount: ₹28,000 (Requires Human Approval)")
res = requests.post("http://localhost:8081/webhook/razorpay", data=body, headers=headers)

if res.status_code == 200:
    print(f"✅ Webhook accepted by Backend: {res.text}")
    print("👉 Now check the 'Approvals' tab on your Dashboard!")
else:
    print(f"❌ Failed: {res.status_code} - {res.text}")
