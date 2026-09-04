import hmac
import hashlib
import json
import requests
import time

# Secret from your .env
secret = "whsec_8b64c1a9d91064227a92bb4d01f05373"

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
