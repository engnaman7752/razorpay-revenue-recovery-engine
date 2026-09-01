# Verify the API keys (run on your own machine)

Neither the Claude sandbox nor the Claude desktop VM can reach
`api.razorpay.com` or `generativelanguage.googleapis.com` — both are outside
their network allowlists. So these two checks have to run in a normal
terminal on your PC.

## 1. Gemini key

PowerShell:

```powershell
$key = "PASTE_GOOGLE_API_KEY"
curl.exe -s -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" `
  -H "x-goog-api-key: $key" -H "Content-Type: application/json" `
  -d '{\"contents\":[{\"parts\":[{\"text\":\"Reply with exactly: OK\"}]}]}'
```

Expect JSON containing `"text": "OK"`.
`API_KEY_INVALID` / 403 means the key is wrong or the Generative Language API
is not enabled on that Google project.

## 2. Razorpay test keys

PowerShell:

```powershell
$id = "PASTE_KEY_ID"; $secret = "PASTE_KEY_SECRET"
curl.exe -s -u "${id}:${secret}" https://api.razorpay.com/v1/payments?count=1
```

Expect `{"entity":"collection","count":...}`.
401 `BAD_REQUEST_ERROR / Authentication failed` means the pair is wrong or the
key was generated in live mode instead of test mode.

## 3. End-to-end, once both pass

```powershell
cd D:\Hackathon\razorpay-recovery
copy env.local.txt .env          # .env is gitignored
docker compose up --build
```

Then the batch (agent must be up) to populate the dashboard:

```powershell
docker compose exec backend java -jar app.jar `
  --recovery.batch.enabled=true --recovery.batch.include-agent=true --server.port=9090
```

With `GOOGLE_API_KEY` set, decide entries in the case timeline show
`mode llm` instead of `mode rule` — that is the proof the LLM path is live.
