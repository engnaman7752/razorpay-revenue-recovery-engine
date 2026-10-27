"""HTTP wrappers around the backend's tool endpoints.

The agent NEVER calls Razorpay and NEVER writes business tables — these six
authenticated endpoints are its only hands. Every call is logged to
decision_log by the backend.
"""

import os
import time

import httpx

BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8080")
AGENT_SHARED_SECRET = os.environ.get("AGENT_SHARED_SECRET", "dev-agent-secret")
TIMEOUT = float(os.environ.get("TOOL_TIMEOUT_SECONDS", "10"))


def _post(path: str, payload: dict, idempotency_key: str | None = None) -> dict:
    headers = {"X-Agent-Secret": AGENT_SHARED_SECRET}
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key
    with httpx.Client(base_url=BACKEND_BASE_URL, timeout=TIMEOUT, headers=headers) as client:
        r = client.post(path, json=payload)
        r.raise_for_status()
        return r.json()


def retry_payment(case_id: str, idempotency_key: str | None = None) -> dict:
    return _post("/internal/tools/retry-payment", {"case_id": case_id}, idempotency_key=idempotency_key)


def schedule_retry(case_id: str, delay_hours: int = 24, idempotency_key: str | None = None) -> dict:
    return _post("/internal/tools/schedule-retry",
                 {"case_id": case_id, "delay_hours": delay_hours},
                 idempotency_key=idempotency_key)


def create_payment_link(case_id: str, idempotency_key: str | None = None) -> dict:
    return _post("/internal/tools/create-payment-link", {"case_id": case_id}, idempotency_key=idempotency_key)


def send_reminder(case_id: str, channel: str = "email", idempotency_key: str | None = None) -> dict:
    return _post("/internal/tools/send-reminder",
                 {"case_id": case_id, "channel": channel},
                 idempotency_key=idempotency_key)


def escalate(case_id: str, reason: str, idempotency_key: str | None = None) -> dict:
    return _post("/internal/tools/escalate", {"case_id": case_id, "reason": reason}, idempotency_key=idempotency_key)


def close_case(case_id: str, reason: str, idempotency_key: str | None = None) -> dict:
    return _post("/internal/tools/close-case", {"case_id": case_id, "reason": reason}, idempotency_key=idempotency_key)


# wire-name -> callable used by the execute node
def execute_action(action: str, case_id: str) -> dict:
    ts_minute = str(int(time.time()) // 60)
    idem_key = f"{case_id}:{action}:{ts_minute}"

    if action == "retry_now":
        return retry_payment(case_id, idempotency_key=idem_key)
    if action == "schedule_retry_24h":
        return schedule_retry(case_id, 24, idempotency_key=idem_key)
    if action == "payment_link":
        return create_payment_link(case_id, idempotency_key=idem_key)
    if action == "reminder_with_link":
        return send_reminder(case_id, "email", idempotency_key=idem_key)
    raise ValueError(f"Not an executable action: {action}")
