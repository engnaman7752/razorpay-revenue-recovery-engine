#!/usr/bin/env bash
# Phase verification script, run by GitHub Actions (ci.yml).
# Grows as phases are added; each phase's checks stay in place so later
# phases can't silently break earlier ones.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "================ PHASE 1: generator ================"
python data/generate.py | tee /tmp/gen.out

# assert the §9 distribution
grep -q "wrote 300 cases" /tmp/gen.out
grep -q "insufficient_fund                    105" /tmp/gen.out
grep -q "opted_out: 6 cases" /tmp/gen.out
echo "generator distribution OK"

echo "================ PHASE 1: backend build (+ unit tests, incl. HMAC verifier) ================"
mvn -B -q -f backend/pom.xml package

echo "================ PHASE 1: backend starts + connects to Postgres ================"
java -jar backend/target/recovery-backend-0.1.0.jar > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
trap 'kill $BACKEND_PID $AGENT_PID $BATCH_PID 2>/dev/null || true' EXIT

for i in $(seq 1 60); do
  if curl -sf http://localhost:8080/api/health > /tmp/health.json; then break; fi
  if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "backend exited early:"; tail -50 /tmp/backend.log; exit 1
  fi
  sleep 2
done

echo "health response:"; cat /tmp/health.json; echo
grep -q '"status":"ok"' /tmp/health.json
grep -E "Flyway|Successfully applied|Migrating" /tmp/backend.log | head -5

echo "================ PHASE 3: agent unit + integration tests ================"
pip install -q -r agent/requirements.txt
(cd agent && python -m pytest tests/ -q)

echo "================ PHASE 3: tool endpoint auth ================"
# no secret -> 401 ; with secret but bogus case -> 404 (auth passed)
code_no_secret=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  http://localhost:8080/internal/tools/close-case \
  -H "Content-Type: application/json" -d '{"case_id":"00000000-0000-0000-0000-000000000000","reason":"x"}')
code_with_secret=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
  http://localhost:8080/internal/tools/close-case \
  -H "Content-Type: application/json" -H "X-Agent-Secret: dev-agent-secret" \
  -d '{"case_id":"00000000-0000-0000-0000-000000000000","reason":"x"}')
echo "no-secret=$code_no_secret with-secret=$code_with_secret"
test "$code_no_secret" = "401"
test "$code_with_secret" = "404"

echo "================ PHASE 2+3: batch (baselines + AGENT) ================"
kill $BACKEND_PID 2>/dev/null || true
wait $BACKEND_PID 2>/dev/null || true

(cd agent && exec env BACKEND_BASE_URL=http://localhost:8081 AGENT_SHARED_SECRET=dev-agent-secret \
  python -m uvicorn main:app --host 127.0.0.1 --port 8000 > /tmp/agent.log 2>&1) &
AGENT_PID=$!
for i in $(seq 1 30); do
  curl -sf http://127.0.0.1:8000/health > /dev/null && break
  sleep 1
done

java -jar backend/target/recovery-backend-0.1.0.jar \
  --recovery.batch.enabled=true --recovery.batch.include-agent=true \
  --server.port=8081 > /tmp/batch.log 2>&1 &
BATCH_PID=$!
for i in $(seq 1 150); do
  grep -q "Batch run .* complete" /tmp/batch.log && break
  if ! kill -0 $BATCH_PID 2>/dev/null; then echo "batch exited early:"; tail -50 /tmp/batch.log; exit 1; fi
  sleep 2
done
kill $BATCH_PID 2>/dev/null || true
grep -q "Batch run .* complete" /tmp/batch.log || { echo "batch never completed:"; tail -50 /tmp/batch.log; exit 1; }

grep "RESULT strategy=" /tmp/batch.log
test -f eval/results.md && { echo "--- eval/results.md ---"; cat eval/results.md; }

# assert ORACLE > AGENT > NAIVE > 0 (baseline paise values are deterministic for seed-42 data)
python3 - <<'PY'
import re
log = open("/tmp/batch.log").read()
res = {m[0]: int(m[1]) for m in re.findall(r"RESULT strategy=(\w+) recovered_paise=(\d+)", log)}
print("parsed:", res)
assert res["DO_NOTHING"] == 0, "DO_NOTHING must recover 0"
assert res["NAIVE"] == 46545000, f"NAIVE expected 46545000, got {res['NAIVE']}"
assert res["ORACLE"] == 154158900, f"ORACLE expected 154158900, got {res['ORACLE']}"
assert res["ORACLE"] > res["AGENT"] > res["NAIVE"] > 0, "need ORACLE > AGENT > NAIVE > 0"
print("phase 2+3 batch numbers OK")
PY

echo "================ PHASE 3: decision_log has rows for every action ================"
export PGPASSWORD=recovery
psql -h localhost -U recovery -d recovery -c \
  "SELECT node, count(*) FROM decision_log GROUP BY node ORDER BY node;"
executed=$(psql -h localhost -U recovery -d recovery -tA -c \
  "SELECT count(*) FROM decision_log WHERE node='execute';")
decides=$(psql -h localhost -U recovery -d recovery -tA -c \
  "SELECT count(*) FROM decision_log WHERE node='decide';")
blocked=$(psql -h localhost -U recovery -d recovery -tA -c \
  "SELECT count(*) FROM decision_log WHERE blocked;")
echo "execute rows=$executed decide rows=$decides blocked rows=$blocked"
test "$executed" -gt 0 && test "$decides" -gt 0 && test "$blocked" -gt 0

echo "================ PHASE 4: learning + governance evidence ================"
# at least one logged EV-abandonment decision
abandoned=$(psql -h localhost -U recovery -d recovery -tA -c \
  "SELECT count(*) FROM decision_log WHERE reasoning LIKE 'abandoned: EV below threshold%';")
# at least one logged guard veto (blocked row with a reason)
vetoes=$(psql -h localhost -U recovery -d recovery -tA -c \
  "SELECT count(*) FROM decision_log WHERE blocked AND block_reason IS NOT NULL;")
# learning table moved away from priors
learned=$(psql -h localhost -U recovery -d recovery -tA -c \
  "SELECT count(*) FROM ev_stats WHERE alpha + beta > 70;")
echo "abandonments=$abandoned vetoes=$vetoes learned_cells=$learned"
test "$abandoned" -gt 0 && test "$vetoes" -gt 0 && test "$learned" -gt 0
grep -q "Learning curve" eval/results.md
grep -q "Per-cause breakdown" eval/results.md

echo "================ PHASE 5: human-in-the-loop survives agent restart ================"
export DB_CONN="-h localhost -U recovery -d recovery"

# restart agent WITH durable checkpoints, and a live-mode backend on 8080
kill $AGENT_PID 2>/dev/null || true; sleep 1
(cd agent && exec env BACKEND_BASE_URL=http://localhost:8080 AGENT_SHARED_SECRET=dev-agent-secret \
  DATABASE_URL=postgresql://recovery:recovery@localhost:5432/recovery \
  python -m uvicorn main:app --host 127.0.0.1 --port 8000 > /tmp/agent5.log 2>&1) &
AGENT_PID=$!
java -jar backend/target/recovery-backend-0.1.0.jar > /tmp/backend5.log 2>&1 &
BACKEND_PID=$!
for i in $(seq 1 60); do
  curl -sf http://localhost:8080/api/health >/dev/null && curl -sf http://127.0.0.1:8000/health >/dev/null && break
  sleep 2
done

# reset one >₹25k case back to DETECTED and run it live (no auto-approval)
CASE_ID=$(psql $DB_CONN -tA -c \
  "SELECT id FROM recovery_case WHERE amount_paise > 2500000 AND (customer_history->>'opted_out')::bool = false LIMIT 1;")
psql $DB_CONN -c "UPDATE recovery_case SET status='DETECTED', attempts=0, contacts_made=0, recovered_paise=0 WHERE id='$CASE_ID';" >/dev/null
echo "high-value case: $CASE_ID"

curl -sf -X POST http://localhost:8080/api/cases/$CASE_ID/process | tee /tmp/process.json; echo
python3 -c "import json;d=json.load(open('/tmp/process.json'));assert d['paused'] and d['status']=='WAITING_APPROVAL', d"
status=$(psql $DB_CONN -tA -c "SELECT status FROM recovery_case WHERE id='$CASE_ID';")
test "$status" = "WAITING_APPROVAL"
curl -sf http://localhost:8080/api/escalations | grep -q "$CASE_ID"
echo "case paused and queued OK"

# --- the demo moment: kill the agent, start a fresh process ---
kill $AGENT_PID 2>/dev/null; sleep 2
(cd agent && exec env BACKEND_BASE_URL=http://localhost:8080 AGENT_SHARED_SECRET=dev-agent-secret \
  DATABASE_URL=postgresql://recovery:recovery@localhost:5432/recovery \
  python -m uvicorn main:app --host 127.0.0.1 --port 8000 > /tmp/agent5b.log 2>&1) &
AGENT_PID=$!
for i in $(seq 1 30); do curl -sf http://127.0.0.1:8000/health >/dev/null && break; sleep 1; done
echo "agent restarted"

curl -sf -X POST http://localhost:8080/api/escalations/$CASE_ID/resolve \
  -H "Content-Type: application/json" -d '{"approved": true}' | tee /tmp/resolve.json; echo
python3 -c "import json;d=json.load(open('/tmp/resolve.json'));assert d['final_status'] in ('RECOVERED','CLOSED'), d"
final=$(psql $DB_CONN -tA -c "SELECT status FROM recovery_case WHERE id='$CASE_ID';")
echo "final status: $final"
test "$final" = "RECOVERED" -o "$final" = "CLOSED"
approved_rows=$(psql $DB_CONN -tA -c \
  "SELECT count(*) FROM decision_log WHERE case_id='$CASE_ID' AND node='human_review' AND outcome='APPROVED';")
test "$approved_rows" -gt 0
echo "resumed from checkpoint after restart OK"

kill $BACKEND_PID 2>/dev/null || true
wait $BACKEND_PID 2>/dev/null || true

echo "================ PHASE 6: webhook -> HMAC verify -> case -> graph ================"
WEBHOOK_SECRET=whsec_ci_test
java -jar backend/target/recovery-backend-0.1.0.jar \
  --recovery.razorpay.webhook-secret=$WEBHOOK_SECRET > /tmp/backend6.log 2>&1 &
BACKEND_PID=$!
for i in $(seq 1 60); do curl -sf http://localhost:8080/api/health >/dev/null && break; sleep 2; done

python3 - "$WEBHOOK_SECRET" <<'PY'
import hashlib, hmac, json, sys
secret = sys.argv[1]
body = json.dumps({
  "event": "payment.failed",
  "payload": {"payment": {"entity": {
      "id": "pay_CI_LIVE_001", "order_id": "order_CI_LIVE_001",
      "amount": 149900, "currency": "INR",
      "error_reason": "insufficient_fund", "error_source": "customer",
      "email": "ci-customer@example.com"}}}
}).encode()
sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
open("/tmp/webhook_body.json", "wb").write(body)
open("/tmp/webhook_sig.txt", "w").write(sig)
PY

# bad signature -> 401 and no case created
code_bad=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8080/webhook/razorpay \
  -H "Content-Type: application/json" -H "X-Razorpay-Signature: deadbeef" \
  --data-binary @/tmp/webhook_body.json)
test "$code_bad" = "401"
# good signature -> 200 + case opened
curl -sf -X POST http://localhost:8080/webhook/razorpay \
  -H "Content-Type: application/json" -H "X-Razorpay-Signature: $(cat /tmp/webhook_sig.txt)" \
  --data-binary @/tmp/webhook_body.json | tee /tmp/webhook_resp.json; echo
LIVE_CASE=$(python3 -c "import json;print(json.load(open('/tmp/webhook_resp.json'))['case_id'])")
echo "live case: $LIVE_CASE"

# the agent picks it up in the background; wait for it to leave DETECTED
for i in $(seq 1 30); do
  s=$(psql $DB_CONN -tA -c "SELECT status FROM recovery_case WHERE id='$LIVE_CASE';")
  [ "$s" != "DETECTED" ] && [ -n "$s" ] && break
  sleep 2
done
echo "live case status after agent: $s"
test "$s" != "DETECTED"
src=$(psql $DB_CONN -tA -c "SELECT source FROM recovery_case WHERE id='$LIVE_CASE';")
test "$src" = "LIVE"
rows=$(psql $DB_CONN -tA -c "SELECT count(*) FROM decision_log WHERE case_id='$LIVE_CASE';")
echo "decision_log rows for live case: $rows"
test "$rows" -gt 2
# duplicate webhook is idempotent
curl -sf -X POST http://localhost:8080/webhook/razorpay \
  -H "Content-Type: application/json" -H "X-Razorpay-Signature: $(cat /tmp/webhook_sig.txt)" \
  --data-binary @/tmp/webhook_body.json | grep -q duplicate
echo "webhook flow OK (401 on bad sig, case created, agent ran, idempotent)"

kill $BACKEND_PID 2>/dev/null || true

echo "================ PHASE 7: frontend builds ================"
(cd frontend && npm install --no-audit --no-fund --silent && npm run build)
test -f frontend/dist/index.html
echo "frontend build OK"

echo "================ ALL PHASE CHECKS PASSED ================"
