"""Full-loop integration: run all 300 synthetic cases through the real graph
against the mock backend (same semantics as the Java ToolController).

Asserts the Phase 3 bar: AGENT beats NAIVE, stays below ORACLE, respects
every stopping rule, and produces a decision trail for every case.
"""

import json
import threading
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from . import mock_backend

CASES_PATH = Path(__file__).parents[2] / "data" / "cases.jsonl"
PORT = 18080
NOON_IST = "2026-08-27T12:00:00+05:30"

# expected values from the deterministic seed-42 dataset (see Phase 2)
NAIVE_RECOVERED_PAISE = 46_545_000
ORACLE_RECOVERED_PAISE = 154_158_900


@pytest.fixture(scope="module")
def stack(monkeypatch_module):
    monkeypatch_module.setenv("BACKEND_BASE_URL", f"http://127.0.0.1:{PORT}")
    monkeypatch_module.setenv("AGENT_SHARED_SECRET", mock_backend.SECRET)

    mock_backend.load_cases(CASES_PATH)
    server = uvicorn.Server(uvicorn.Config(mock_backend.app, host="127.0.0.1",
                                           port=PORT, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        try:
            httpx.get(f"http://127.0.0.1:{PORT}/docs", timeout=1)
            break
        except httpx.HTTPError:
            time.sleep(0.1)

    # import AFTER env is set so tools.py picks up the mock URL
    import importlib
    from graph import tools
    importlib.reload(tools)
    from graph import build, nodes
    importlib.reload(nodes)
    graph = build.build_graph()

    yield graph
    server.should_exit = True


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.fixture(scope="module")
def batch_results(stack):
    import yaml
    policy = yaml.safe_load((Path(__file__).parents[1] / "policy.yaml").read_text())
    config = {"configurable": {"policy": policy}}

    finals = []
    for c in mock_backend.CASES.values():
        state = {
            "case_id": c["id"],
            "amount_paise": c["amount_paise"],
            "error_reason": c["error_reason"],
            "opted_out": c["customer_history"]["opted_out"],
            "attempts": 0, "contacts_made": 0,
            "auto_approve": True, "now_iso": NOON_IST,
            "actions": [], "trace": [],
        }
        # Phase 4: pass the current learned stats, exactly like AgentClient does
        config["configurable"]["ev_stats"] = mock_backend.stats_wire()
        finals.append(stack.invoke(state, config))
    return finals


def test_agent_beats_naive_and_trails_oracle(batch_results):
    recovered = sum(c["recovered_paise"] for c in mock_backend.CASES.values())
    print(f"\nAGENT recovered: ₹{recovered/100:,.0f} "
          f"(NAIVE ₹{NAIVE_RECOVERED_PAISE/100:,.0f}, ORACLE ₹{ORACLE_RECOVERED_PAISE/100:,.0f})")
    assert recovered > NAIVE_RECOVERED_PAISE
    assert recovered < ORACLE_RECOVERED_PAISE


def test_every_case_reaches_a_terminal_state(batch_results):
    for f in batch_results:
        assert f["status"] in ("RECOVERED", "CLOSED", "ESCALATED"), f["status"]


def test_stopping_rules_hold(batch_results):
    for c in mock_backend.CASES.values():
        assert c["attempts"] <= 3, f"attempts cap broken on {c['id']}"
        assert c["contacts_made"] <= 2, f"contact cap broken on {c['id']}"


def test_opted_out_customers_never_touched(batch_results):
    for c in mock_backend.CASES.values():
        if c["customer_history"]["opted_out"]:
            assert c["attempts"] == 0 and c["contacts_made"] == 0


def test_high_value_cases_get_escalation_entries(batch_results):
    high = [f for f in batch_results
            if f["amount_paise"] > 25_000_00]
    assert high, "dataset should contain >₹25k cases"
    for f in high:
        if f.get("opted_out"):
            continue
        assert f.get("escalated"), f"high-value case {f['case_id']} not escalated"


def test_ev_abandonment_happens_and_is_logged(batch_results):
    abandoned = [f for f in batch_results
                 if "abandoned: EV below threshold" in f.get("close_reason", "")]
    assert abandoned, "expected some low-value cases to be EV-abandoned"


def test_every_action_is_in_the_decision_log(batch_results):
    total_actions = sum(len(f.get("actions", [])) for f in batch_results)
    executed = [e for e in mock_backend.DECISION_LOG if e["node"] == "execute"
                and e["action"] not in ("escalate", "close_case")]
    assert total_actions == len(executed)


def test_trace_exists_for_every_case(batch_results):
    for f in batch_results:
        nodes_seen = {e["node"] for e in f["trace"]}
        assert "diagnose" in nodes_seen and "decide" in nodes_seen


# ------------------------------------------------------- Phase 4: learning
def test_learning_updates_ev_stats(batch_results):
    from graph import ev as ev_module
    changed = sum(1 for key, ab in mock_backend.EV_STATS.items()
                  if tuple(ab) != ev_module.PRIORS.get(key, (1, 49)))
    assert changed >= 10, "expected many (cause, action) cells to have learned counts"


def test_learning_reduces_wasted_contacts(batch_results):
    """The generator gives some (cause, action) pairs a true success rate of ~0
    while their prior is optimistic (e.g. HARD_DECLINE + reminder). As beta
    grows, those actions drop in the ranking and stop being tried, so contact
    spend per case should fall from the first third to the last third."""
    ordered = list(mock_backend.CASES.values())
    thirds = [ordered[0:100], ordered[100:200], ordered[200:300]]
    contacts = [sum(c["contacts_made"] for c in t) for t in thirds]
    print(f"\ncontacts per third: {contacts}")
    assert contacts[2] < contacts[0], "learning should cut wasted contacts over time"
