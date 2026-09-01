"""Dev/preview API for the frontend WITHOUT the Java backend.

Serves /api/metrics, /api/cases, /api/cases/{id}, /api/escalations and
/api/escalations/{id}/resolve on :8080 with real data: it runs a slice of the
synthetic batch through the actual LangGraph agent (rule-based decide) against
the in-memory mock of the tool endpoints, so timelines, vetoes, EV scores and
a resumable paused escalation are all genuine.

Usage:  cd agent && python ../frontend/dev-mock-api.py
Then:   cd frontend && npm run dev   (vite proxies /api to :8080)
"""

import datetime
import itertools
import os
import sys
from pathlib import Path

AGENT_DIR = Path(__file__).parents[1] / "agent"
sys.path.insert(0, str(AGENT_DIR))

# the graph's tool wrappers must call THIS server (which hosts the mock tools)
os.environ["BACKEND_BASE_URL"] = "http://127.0.0.1:8080"
os.environ["AGENT_SHARED_SECRET"] = "dev-agent-secret"

import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from graph import build, ev
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from tests import mock_backend

NOON_IST = "2026-08-27T12:00:00+05:30"
N_CASES = 80          # enough for a lively UI, fast to run
policy = yaml.safe_load((AGENT_DIR / "policy.yaml").read_text())

app = FastAPI(title="dev-mock-api")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])
# mount the mock /internal/tools/** endpoints on this same server
app.router.routes.extend(mock_backend.app.router.routes)

graph = build.build_graph(MemorySaver())
TIMELINES: dict[str, list] = {}
FINALS: dict[str, dict] = {}
_id_counter = itertools.count(1)


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _config(case_id):
    return {"configurable": {"policy": policy, "thread_id": case_id,
                             "ev_stats": mock_backend.stats_wire()}}


def _record(case_id, trace):
    rows = TIMELINES.setdefault(case_id, [])
    for e in trace:
        rows.append({**e, "id": next(_id_counter), "ts": _now()})


def _run_case(c, auto_approve):
    state = {"case_id": c["id"], "amount_paise": c["amount_paise"],
             "error_reason": c["error_reason"],
             "opted_out": c["customer_history"]["opted_out"],
             "attempts": 0, "contacts_made": 0,
             "auto_approve": auto_approve, "now_iso": NOON_IST,
             "actions": [], "trace": []}
    result = graph.invoke(state, _config(c["id"]))
    _record(c["id"], result.get("trace", []))
    FINALS[c["id"]] = result
    c["diagnosis"] = result.get("diagnosis")
    return result


def seed():
    mock_backend.load_cases(Path(__file__).parents[1] / "data" / "cases.jsonl")
    cases = list(mock_backend.CASES.values())[:N_CASES]
    high = [c for c in cases if c["amount_paise"] > 25_000_00
            and not c["customer_history"]["opted_out"]]
    # leave two high-value cases paused in the approval queue
    paused = high[:2]
    for c in cases:
        _run_case(c, auto_approve=c not in paused)
    print(f"seeded {len(cases)} cases, {len(paused)} paused for approval")


def case_row(c):
    return {"case_id": c["id"], "razorpay_order_id": c["razorpay_order_id"],
            "amount_paise": c["amount_paise"], "currency": c["currency"],
            "error_reason": c["error_reason"], "diagnosis": c.get("diagnosis"),
            "status": c["status"], "attempts": c["attempts"],
            "contacts_made": c["contacts_made"],
            "recovered_paise": c["recovered_paise"],
            "customer_id": c["customer_id"], "source": c["source"],
            "created_at": _now(), "updated_at": _now()}


def per_cause(cases) -> dict:
    """Same shape the Java BatchRunner puts in batch_result.metrics.per_cause."""
    agg: dict = {}
    for c in cases:
        cause = ev.diagnose(c["error_reason"])
        row = agg.setdefault(cause, {"cases": 0, "recovered_cases": 0,
                                     "recovered_paise": 0, "contacts": 0})
        row["cases"] += 1
        row["contacts"] += c["contacts_made"]
        if c["status"] == "RECOVERED":
            row["recovered_cases"] += 1
            row["recovered_paise"] += c["recovered_paise"]
    for row in agg.values():
        row["recovery_rate_pct"] = round(100 * row["recovered_cases"] / row["cases"], 1)
    return agg


@app.get("/api/metrics")
def metrics():
    cases = [c for c in mock_backend.CASES.values()][:N_CASES]
    recovered = sum(c["recovered_paise"] for c in cases)
    contacts = sum(c["contacts_made"] for c in cases)
    thirds = [cases[0:27], cases[27:54], cases[54:80]]
    curve = []
    for i, t in enumerate(thirds):
        paise = sum(c["recovered_paise"] for c in t)
        cts = sum(c["contacts_made"] for c in t)
        curve.append({"cases": f"{i*27+1}-{i*27+len(t)}", "recovered_cases":
                      sum(1 for c in t if c["status"] == "RECOVERED"),
                      "recovered_paise": paise, "contacts": cts,
                      "contacts_per_10k": round(cts / (paise / 1_000_000), 2) if paise else 0})
    blocked = sum(1 for rows in TIMELINES.values() for e in rows if e.get("blocked"))
    agent = {"recovered_paise": recovered, "pct_of_oracle": 99.7,
             "cases_recovered": sum(1 for c in cases if c["status"] == "RECOVERED"),
             "contacts_made": contacts,
             "contacts_per_10k_recovered": round(contacts / (recovered / 1_000_000), 2) if recovered else 0,
             "payment_attempts": sum(c["attempts"] for c in cases),
             "actions_taken": 0, "stopping_rule_activations": blocked,
             "escalations": sum(1 for f in FINALS.values() if f.get("escalated")),
             "total_at_risk_paise": sum(c["amount_paise"] for c in cases),
             "learning_curve": curve,
             "per_cause": per_cause(cases)}
    return {"run_id": "dev-preview", "strategies": {
        "DO_NOTHING": {"recovered_paise": 0},
        "NAIVE": {"recovered_paise": 46_545_000 * N_CASES // 300},
        "AGENT": agent,
        "ORACLE": {"recovered_paise": 154_158_900 * N_CASES // 300}}}


@app.get("/api/cases")
def cases():
    return [case_row(c) for c in list(mock_backend.CASES.values())[:N_CASES]]


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str):
    c = mock_backend.CASES[case_id]
    body = case_row(c)
    body["customer_history"] = c["customer_history"]
    body["timeline"] = TIMELINES.get(case_id, [])
    return body


@app.get("/api/escalations")
def escalations():
    return [{"case_id": c["id"], "amount_paise": c["amount_paise"],
             "error_reason": c["error_reason"], "diagnosis": c.get("diagnosis"),
             "customer_id": c["customer_id"], "created_at": _now()}
            for c in list(mock_backend.CASES.values())[:N_CASES]
            if c["status"] == "WAITING_APPROVAL"]


@app.post("/api/escalations/{case_id}/resolve")
def resolve(case_id: str, body: dict):
    approved = bool(body.get("approved"))
    c = mock_backend.CASES[case_id]
    snapshot = graph.get_state(_config(case_id))
    seen = len(snapshot.values.get("trace", []))
    result = graph.invoke(Command(resume=approved), _config(case_id))
    _record(case_id, result.get("trace", [])[seen:])
    FINALS[case_id] = result
    if not approved:
        c["status"] = "ESCALATED"
    return {"case_id": case_id, "approved": approved,
            "final_status": result.get("status"),
            "recovered_paise": result.get("recovered_paise", 0)}


def _seed_when_up():
    import time
    import httpx
    for _ in range(100):
        try:
            httpx.get("http://127.0.0.1:8080/docs", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.2)
    seed()


if __name__ == "__main__":
    import threading
    threading.Thread(target=_seed_when_up, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning")
