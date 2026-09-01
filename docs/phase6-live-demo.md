# Phase 6 — live Razorpay test-mode demo (run on your machine)

## One-time setup

1. Razorpay Dashboard (test mode) → Settings → API Keys → generate. Put into `.env`:
   ```
   RAZORPAY_KEY_ID=rzp_test_...
   RAZORPAY_KEY_SECRET=...
   GATEWAY_MODE=live
   ```
2. Expose the backend to the internet for webhooks (any tunnel works):
   ```
   ngrok http 8080
   ```
3. Dashboard → Settings → Webhooks → Add:
   - URL: `https://<your-tunnel>/webhook/razorpay`
   - Secret: pick one, put the same value in `.env` as `RAZORPAY_WEBHOOK_SECRET=...`
   - Events: `payment.failed`, `payment_link.paid`, `order.paid`

## The demo

1. `docker compose up --build` (or run postgres + backend + agent manually).
2. Create a test payment and fail it with an error-simulation card
   (Razorpay test cards, e.g. the "card declined" / "insufficient funds" numbers
   from https://razorpay.com/docs/payments/payments/test-card-details/), or use
   the Dashboard's webhook test to send a `payment.failed` event.
3. Watch the flow:
   - backend log: `LIVE case <id> opened for failed payment pay_...`
   - the agent diagnoses and decides; for a HARD_DECLINE you'll see
     `payment link created: https://rzp.io/... (awaiting payment webhook)`
     in the decision log (`GET /api/cases/<id>` → timeline).
   - open the payment link, pay with a SUCCESS test card →
     Razorpay sends `payment_link.paid` → the case flips to RECOVERED.

## Notes

- A >₹25,000 failed payment pauses at human_review instead: approve it via
  `POST /api/escalations/<id>/resolve {"approved": true}` or the dashboard (Phase 7).
- Signature check is over the raw request body; if you proxy the webhook,
  make sure nothing rewrites the payload bytes.
