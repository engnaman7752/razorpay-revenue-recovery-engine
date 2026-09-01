"""Phase 5: human-in-the-loop.

Runs a >₹25,000 case with auto_approve=False against real Postgres checkpoints:
the graph must pause at human_review, the pause must survive a simulated agent
restart (a brand-new graph + checkpointer connection), and Command(resume=...)
must complete the case from the checkpoint.

Requires a local Postgres with the recovery db (same as docker-compose / CI).
Skips cleanly if Postgres is unreachable.
"""

import os
import threading
import time
import uuid

import httpx
import pytest
import uvicorn
import yaml
from pathlib import Path

from . import mock_backend

DB_URL = os.environ.get("TEST_DATABASE_URL",
                        "postgresql://recovery:recovery@localhost:5432/recovery")
PORT = 18090
NOON_IST = "2026-08-27T12:00:00+05:30"


def _postgres_available() -> bool:
    try:
        import psycopg
        with psycopg.connect(DB_URL, connect_timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _postgres_available(),
                                reason="local Postgres not available")


def _make_graph():
    """Fresh checkpointer + fresh graph — what a restarted agent process builds."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg import Connection
    from psycopg.rows import dict_row
    conn = Connection.connect(DB_URL, autocommit=True, row_factory=dict_row)
    saver = PostgresSaver(conn)
    saver.setup()
    from graph import build
    return build.build_graph(saver), saver


@pytest.fixture(scope="module")
def backend():
    os.environ["BACKEND_BASE_URL"] = f"http://127.0.0.1:{PORT}"
    os.environ["AGENT_SHARED_SECRET"] = mock_backend.SECRET
    import importlib
    from graph import tools
    importlib.reload(tools)

    mock_backend.load_cases(Path(__file__).parents[2] / "data" / "cases.jsonl")
    server = uvicorn.Server(uvicorn.Config(mock_backend.app, host="127.0.0.1",
                                           port=PORT, log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(50):
        try:
            httpx.get(f"http://127.0.0.1:{PORT}/docs", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.1)
    yield
    server.should_exit = True


def _high_value_case():
    c = next(c for c in mock_backend.CASES.values()
             if c["amount_paise"] > 25_000_00
             and not c["customer_history"]["opted_out"]
             and c["ground_truth"]["recoverable"])
    # reset from any earlier test run
    c.update(status="DETECTED", attempts=0, contacts_made=0, recovered_paise=0)
    return c


def _initial(c, thread_id):
    state = {
        "case_id": c["id"], "amount_paise": c["amount_paise"],
        "error_reason": c["error_reason"],
        "opted_out": c["customer_history"]["opted_out"],
        "attempts": 0, "contacts_made": 0,
        "auto_approve": False, "now_iso": NOON_IST,
        "actions": [], "trace": [],
    }
    policy = yaml.safe_load((Path(__file__).parents[1] / "policy.yaml").read_text())
    config = {"configurable": {"policy": policy, "thread_id": thread_id}}
    return state, config


def test_pause_survives_restart_and_approval_completes(backend):
    from langgraph.types import Command

    c = _high_value_case()
    thread_id = f"test-approve-{uuid.uuid4()}"
    graph1, _ = _make_graph()
    state, config = _initial(c, thread_id)

    result = graph1.invoke(state, config)
    assert "__interrupt__" in result, "high-value case must pause for approval"
    assert c["status"] == "WAITING_APPROVAL", "case must be parked in the human queue"

    # --- simulated agent restart: brand-new process state ---
    graph2, _ = _make_graph()
    snapshot = graph2.get_state(config)
    assert snapshot.next, "checkpoint must still be paused after restart"

    final = graph2.invoke(Command(resume=True), config)
    assert "__interrupt__" not in final
    assert final["status"] in ("RECOVERED", "CLOSED")
    outcomes = [e for e in final["trace"] if e["node"] == "human_review"]
    assert outcomes and outcomes[-1]["outcome"] == "APPROVED"
    assert c["status"] == "RECOVERED", "recoverable case should recover after approval"


def test_rejection_stops_the_case(backend):
    from langgraph.types import Command

    c = _high_value_case()
    thread_id = f"test-reject-{uuid.uuid4()}"
    graph1, _ = _make_graph()
    state, config = _initial(c, thread_id)

    result = graph1.invoke(state, config)
    assert "__interrupt__" in result

    graph2, _ = _make_graph()
    final = graph2.invoke(Command(resume=False), config)
    assert final["status"] == "ESCALATED"
    assert final["close_reason"] == "escalation rejected by human"
    assert c["attempts"] == 0 and c["contacts_made"] == 0, \
        "no action may run on a rejected case"


def test_full_service_flow_decide_then_resume(backend):
    """Same thing through the FastAPI endpoints (what the backend actually calls)."""
    import importlib
    os.environ["DATABASE_URL"] = DB_URL
    import main as main_module
    main_module = importlib.reload(main_module)
    from fastapi.testclient import TestClient
    client = TestClient(main_module.app)

    c = _high_value_case()
    body = {"case_id": c["id"], "amount_paise": c["amount_paise"],
            "error_reason": c["error_reason"], "opted_out": False,
            "attempts": 0, "contacts_made": 0,
            "auto_approve": False, "now": NOON_IST}

    r1 = client.post("/decide", json=body).json()
    assert r1["paused"] and r1["status"] == "WAITING_APPROVAL"
    pre_pause_trace = len(r1["trace"])

    r2 = client.post("/resume", json={"case_id": c["id"], "approved": True}).json()
    assert not r2["paused"]
    assert r2["status"] in ("RECOVERED", "CLOSED")
    # /resume returns only NEW entries (no double logging on the backend)
    assert all(e["node"] != "diagnose" for e in r2["trace"])
    assert any(e["node"] == "human_review" for e in r2["trace"])
    assert len(r2["trace"]) > 0 and pre_pause_trace > 0

    r3 = client.post("/resume", json={"case_id": c["id"], "approved": True})
    assert r3.status_code == 409, "resuming a finished case must 409"
