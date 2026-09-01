"""HTTP wrappers around the backend's tool endpoints.

The agent NEVER calls Razorpay and NEVER writes business tables — these six
authenticated endpoints are its only hands. Every call is logged to
decision_log by the backend.
"""

import os

import httpx

BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8080")
AGENT_SHARED_SECRET = os.environ.get("AGENT_SHARED_SECRET", "dev-agent-secret")
TIMEOUT = float(os.environ.get("TOOL_TIMEOUT_SECONDS", "10"))


def _post(path: str, payload: dict) -> dict:
    with httpx.Client(timeout=TIMEOUT) as client:
        response = client.post(
            f"{BACKEND_BASE_URL}{path}",
            json=payload,
            headers={"X-Agent-Secret": AGENT_SHARED_SECRET},
        )
        response.raise_for_status()
        return response.json()


def retry_payment(case_id: str) -> dict:
    return _post("/internal/tools/retry-payment", {"case_id": case_id})


def schedule_retry(case_id: str, delay_hours: int = 24) -> dict:
    return _post("/internal/tools/schedule-retry",
                 {"case_id": case_id, "delay_hours": delay_hours})


def create_payment_link(case_id: str) -> dict:
    return _post("/internal/tools/create-payment-link", {"case_id": case_id})


def send_reminder(case_id: str, channel: str = "email") -> dict:
    return _post("/internal/tools/send-reminder",
                 {"case_id": case_id, "channel": channel})


def escalate(case_id: str, reason: str) -> dict:
    return _post("/internal/tools/escalate", {"case_id": case_id, "reason": reason})


def close_case(case_id: str, reason: str) -> dict:
    return _post("/internal/tools/close-case", {"case_id": case_id, "reason": reason})


# wire-name -> callable used by the execute node
def execute_action(action: str, case_id: str) -> dict:
    if action == "retry_now":
        return retry_payment(case_id)
    if action == "schedule_retry_24h":
        return schedule_retry(case_id, 24)
    if action == "payment_link":
        return create_payment_link(case_id)
    if action == "reminder_with_link":
        return send_reminder(case_id, "email")
    raise ValueError(f"Not an executable action: {action}")
