# Manual Razorpay interaction — doing it by hand, live

Three levels. Level 1 takes two minutes and needs nothing. Level 3 is the full
loop and is what actually wins the "is this real?" argument.

Everything is Razorpay **test mode**. No real money moves at any point.

---

## Level 1 · Prove the keys and the API calls are real (2 min, no setup)

```powershell
cd D:\Hackathon\razorpay-recovery
python scripts\razorpay_smoke.py
```

This hits `https://api.razorpay.com/v1` with your keys and does exactly the
three things the backend does in live mode:

1. `GET /payments` — authenticates
2. `POST /orders` — the call `RETRY_NOW` makes
3. `POST /payment_links` — the call `PAYMENT_LINK` makes

It prints a real `https://rzp.io/...` URL. **Open it in a browser.** That is a
genuine Razorpay-hosted checkout page with your merchant name on it.

The script refuses to run if your key doesn't start with `rzp_test_`.

> In front of judges this is the answer to "did you actually integrate
> Razorpay or just mock it?" — run it live, open the link.

---

## Level 2 · Poke the API by hand with curl (understand the shapes)

Same calls, no Python. In PowerShell:

```powershell
$env:KEY = "rzp_test_TWO4ywTimLqedE"
$env:SEC = "<your RAZORPAY_KEY_SECRET from .env>"
$pair = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$env:KEY`:$env:SEC"))
$h = @{ Authorization = "Basic $pair" }

# create an order (this is retry_now)
Invoke-RestMethod -Method Post -Uri "https://api.razorpay.com/v1/orders" -Headers $h `
  -ContentType "application/json" `
  -Body '{"amount":249900,"currency":"INR","receipt":"manual-test-1"}'

# create a payment link (this is payment_link)
Invoke-RestMethod -Method Post -Uri "https://api.razorpay.com/v1/payment_links" -Headers $h `
  -ContentType "application/json" `
  -Body '{"amount":249900,"currency":"INR","description":"Complete your failed payment","reference_id":"manual-test-1","notify":{"sms":false,"email":false}}'
```

The `short_url` in the response is the payment link. `notify:{sms:false,email:false}`
matters — without it Razorpay will actually text and email the customer.

Everything you create here shows up in **Razorpay Dashboard → Test Mode →
Transactions / Payment Links**. That dashboard view is itself good demo
material: your app's calls, visible in Razorpay's own UI.

---

## Level 3 · The full loop: real failed payment → agent → real recovery

This is the one where Razorpay drives your system and your system drives
Razorpay back. Takes about 10 minutes to set up once.

### 3a. Switch to live gateway mode

In `.env`:

```
GATEWAY_MODE=live
```

Restart the backend. (Leave it `simulated` for the 300-case benchmark — the
benchmark must not depend on the network, and the comparison is only fair if
every strategy faces the same deterministic gateway.)

### 3b. Expose your backend to the internet

Razorpay has to reach your laptop. Your backend is on the port set by
`SERVER_PORT` in `.env` — currently **8081**:

```powershell
ngrok http 8081
```

Copy the `https://xxxx.ngrok-free.app` URL it prints.

### 3c. Register the webhook

Razorpay Dashboard → **Settings → Webhooks → Add New Webhook**

- **URL:** `https://xxxx.ngrok-free.app/webhook/razorpay`
- **Secret:** paste the value of `RAZORPAY_WEBHOOK_SECRET` from your `.env`
  (they must match exactly — the backend verifies an HMAC-SHA256 over the raw
  request bytes and returns 401 on any mismatch)
- **Active events:** tick exactly these three
  - `payment.failed`
  - `payment_link.paid`
  - `order.paid`

### 3d. Create a payment and deliberately fail it

Easiest path, no card details needed — use Razorpay's test UPI IDs:

| UPI ID | Result |
|---|---|
| `failure@razorpay` | payment fails |
| `success@razorpay` | payment succeeds |

Open any payment link you created in Level 1 or 2, choose UPI, enter
`failure@razorpay`, submit. For cards instead, the test-card table is at
<https://razorpay.com/docs/payments/payments/test-card-details/> — any random
CVV and any future expiry date.

You can also skip the checkout entirely: **Dashboard → Settings → Webhooks →
your webhook → Test Webhook** sends a sample `payment.failed` event straight at
your backend. Faster to demo, and it exercises the same signature check.

### 3e. Watch your system react

In the backend log:

```
LIVE case 7f3c… opened for failed payment pay_XXXXXXXX
```

Then the agent takes over. Open the case in the dashboard
(`http://localhost:5173` → Cases → that case) and read the timeline:
`diagnose → decide → guard → execute`. In the execute row you'll see the real
artefact it created:

```
payment link created: https://rzp.io/... (awaiting payment webhook)
```

**That link is real.** Open it. Pay with `success@razorpay`. Razorpay fires
`payment_link.paid` → your webhook matches it back to the case via
`reference_id` → the case flips to **RECOVERED** on the dashboard while the
judges watch.

That is the whole thesis of the project executing end to end, with Razorpay on
both ends of it.

> If the failed payment is above ₹25,000 the graph will pause at `human_review`
> instead of acting. That's the governance rule working, not a bug — approve it
> in the Approvals tab and the agent resumes from its Postgres checkpoint.

---

## How the correlation works (worth being able to explain)

Razorpay has no idea what a "recovery case" is, so the code smuggles the case
id through fields Razorpay does round-trip:

| Action | Field carrying the case id | Webhook that comes back |
|---|---|---|
| `RETRY_NOW`, `SCHEDULE_RETRY_24H` | order `receipt` | `order.paid` |
| `PAYMENT_LINK`, `REMINDER_WITH_LINK` | link `reference_id` (`<case-id>:<timestamp>`) | `payment_link.paid` |

Live actions all return **PENDING**, never "recovered" — creating a link does
not recover money. Only the webhook can mark a case `RECOVERED`. That
distinction is why `LiveRazorpayGateway` returns `GatewayResult.pending(...)`
everywhere, and it's a good detail to point out if a judge asks how you avoid
counting optimistic outcomes.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| webhook returns 401 | `RAZORPAY_WEBHOOK_SECRET` in `.env` ≠ the secret in the Razorpay dashboard |
| nothing arrives at all | ngrok URL changed (it changes on every restart) — re-register it |
| `live gateway: RAZORPAY_KEY_ID/SECRET not configured` | backend started before `.env` had the keys — restart it |
| actions still say "simulated" | `GATEWAY_MODE` is still `simulated`, or backend wasn't restarted after changing it |
| link created but case never recovers | you paid it, but the webhook can't reach you — check the ngrok request log |

---

## The setup harness — `scripts/webhook_setup.py`

Four commands. Run them in this order and the loop is set up and rehearsed.

```powershell
python scripts\webhook_setup.py check      # keys, GATEWAY_MODE, backend, agent, tunnel
python scripts\webhook_setup.py url        # exact URL + secret to paste into Razorpay
python scripts\webhook_setup.py selftest   # fake a payment.failed and watch the agent work it
python scripts\webhook_setup.py pay <id>   # fake the payment_link.paid, case -> RECOVERED
```

`selftest` and `pay` sign events with your own `RAZORPAY_WEBHOOK_SECRET` and
POST them at your backend exactly the way Razorpay does — same HMAC-SHA256 over
the same raw bytes, same headers. So you can rehearse the entire loop with **no
ngrok, no internet, and no spent test payment**.

`selftest` also sends a deliberately forged signature first and asserts the
backend answers **401**. If that check ever stops passing, your webhook endpoint
is accepting unsigned events — which would be the single worst bug in this
codebase, so it is worth having a command that proves it doesn't.

Once `selftest` passes, the only remaining failure mode on demo day is the
tunnel. That's why `check` looks for ngrok separately.

### In VS Code

Ctrl+Shift+P → Tasks: Run Task →

- **Webhook · 1 start ngrok tunnel** (leave running)
- **Webhook · 2 show what to paste into Razorpay**
- **Webhook · 3 self-test the whole loop**
- **Webhook · check config**
