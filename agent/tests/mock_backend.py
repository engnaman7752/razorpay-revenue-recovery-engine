"""In-memory stand-in for the Java backend's /internal/tools/** endpoints.

Mirrors ToolController semantics exactly (same SimulatedGateway rule:
an action succeeds iff it equals ground_truth.recovers_if). Used by the
integration test and handy for demoing the agent without the JVM.
"""

import json
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException

from graph import ev as ev_module

SECRET = "dev-agent-secret"

app = FastAPI(title="mock-backend")
CASES: dict[str, dict] = {}
DECISION_LOG: list[dict] = []
EV_STATS: dict = {}   # {(cause, action): [alpha, beta]} — Beta-Bernoulli learning


def reset_ev_stats():
    EV_STATS.clear()
    for key, (alpha, beta) in ev_module.PRIORS.items():
        EV_STATS[key] = [alpha, beta]


def record_outcome(c: dict, action: str, success: bool):
    """Mirror of the backend's EvStatsService.recordOutcome."""
    cause = ev_module.diagnose(c["error_reason"])
    alpha, beta = EV_STATS.get((cause, action), (1, 49))
    EV_STATS[(cause, action)] = [alpha + 1, beta] if success else [alpha, beta + 1]


def stats_wire() -> dict:
    """The shape AgentClient sends in /decide: {cause: {action: [alpha, beta]}}."""
    wire: dict = {}
    for (cause, action), ab in EV_STATS.items():
        wire.setdefault(cause, {})[action] = list(ab)
    return wire


def load_cases(path: str | Path):
    CASES.clear()
    DECISION_LOG.clear()
    reset_ev_stats()
    for line in Path(path).read_text().splitlines():
        if line.strip():
            c = json.loads(line)
            c["status"] = "DETECTED"
            c["attempts"] = 0
            c["contacts_made"] = 0
            c["recovered_paise"] = 0
            CASES[c["id"]] = c


def _auth(secret: str | None):
    if secret != SECRET:
        raise HTTPException(status_code=401, detail="bad X-Agent-Secret")


def _case(case_id: str) -> dict:
    if case_id not in CASES:
        raise HTTPException(status_code=404, detail="no such case")
    return CASES[case_id]


def _resolve(c: dict, action: str) -> bool:
    return c["ground_truth"]["recovers_if"] == action


def _log(c, action, outcome, attempt=None):
    DECISION_LOG.append({"case_id": c["id"], "node": "execute",
                         "action": action, "outcome": outcome, "attempt": attempt})


def _respond(c: dict, outcome: str) -> dict:
    return {"outcome": outcome, "status": c["status"], "attempts": c["attempts"],
            "contacts_made": c["contacts_made"], "recovered_paise": c["recovered_paise"]}


def _attempt_payment(c: dict, action: str) -> dict:
    c["attempts"] += 1
    success = _resolve(c, action)
    if success:
        c["status"] = "RECOVERED"
        c["recovered_paise"] = c["amount_paise"]
    record_outcome(c, action, success)
    _log(c, action, "RECOVERED" if success else "FAILED", c["attempts"])
    return _respond(c, "RECOVERED" if success else "FAILED")


def _contact(c: dict, action: str) -> dict:
    c["contacts_made"] += 1
    success = _resolve(c, action)
    if success:
        c["status"] = "RECOVERED"
        c["recovered_paise"] = c["amount_paise"]
    record_outcome(c, action, success)
    _log(c, action, "RECOVERED" if success else "FAILED")
    return _respond(c, "RECOVERED" if success else "FAILED")


@app.post("/internal/tools/retry-payment")
def retry_payment(body: dict, x_agent_secret: str | None = Header(default=None)):
    _auth(x_agent_secret)
    return _attempt_payment(_case(body["case_id"]), "retry_now")


@app.post("/internal/tools/schedule-retry")
def schedule_retry(body: dict, x_agent_secret: str | None = Header(default=None)):
    _auth(x_agent_secret)
    # simulated mode collapses time: the 24h retry resolves immediately
    return _attempt_payment(_case(body["case_id"]), "schedule_retry_24h")


@app.post("/internal/tools/create-payment-link")
def create_payment_link(body: dict, x_agent_secret: str | None = Header(default=None)):
    _auth(x_agent_secret)
    return _contact(_case(body["case_id"]), "payment_link")


@app.post("/internal/tools/send-reminder")
def send_reminder(body: dict, x_agent_secret: str | None = Header(default=None)):
    _auth(x_agent_secret)
    return _contact(_case(body["case_id"]), "reminder_with_link")


@app.post("/internal/tools/escalate")
def escalate(body: dict, x_agent_secret: str | None = Header(default=None)):
    _auth(x_agent_secret)
    c = _case(body["case_id"])
    c["status"] = "WAITING_APPROVAL"   # parked in the human queue
    _log(c, "escalate", "WAITING_APPROVAL")
    return _respond(c, "WAITING_APPROVAL")


@app.post("/internal/tools/close-case")
def close_case(body: dict, x_agent_secret: str | None = Header(default=None)):
    _auth(x_agent_secret)
    c = _case(body["case_id"])
    if c["status"] not in ("RECOVERED", "ESCALATED"):
        c["status"] = "CLOSED"
    _log(c, "close_case", "CLOSED")
    return _respond(c, "CLOSED")
