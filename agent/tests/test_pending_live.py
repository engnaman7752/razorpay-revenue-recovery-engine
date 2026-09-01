"""Live-mode PENDING semantics: an initiated-but-unresolved action (retry
order / payment link awaiting its webhook) must end the graph run WITHOUT
closing the case and WITHOUT teaching the learning table a failure."""

from graph import nodes


def test_pending_outcome_routes_to_close_not_redecide():
    updates = nodes.check_outcome({"last_outcome": "PENDING", "status": "IN_PROGRESS",
                                   "chosen_action": "payment_link"})
    assert updates["outcome_route"] == "close"
    # a pending action was not a failure: it must NOT be vetoed for retry later
    assert "vetoed_actions" not in updates


def test_close_leaves_pending_case_open():
    updates = nodes.close({"case_id": "x", "status": "IN_PROGRESS",
                           "last_outcome": "PENDING"})
    assert "status" not in updates          # stays IN_PROGRESS, not CLOSED
    entry = updates["trace"][0]
    assert entry["outcome"] == "PENDING"
    assert "awaiting webhook" in entry["reasoning"]


def test_failed_outcome_still_redecides_and_vetoes():
    updates = nodes.check_outcome({"last_outcome": "FAILED", "status": "IN_PROGRESS",
                                   "chosen_action": "retry_now"})
    assert updates["outcome_route"] == "decide"
    assert updates["vetoed_actions"] == ["retry_now"]
