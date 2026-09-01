"""Graph nodes. Phase 3: decide is RULE-BASED (top expected value).
Phase 4 swaps the chooser for an LLM; everything else stays identical.

Every node appends decision_log-shaped entries to state["trace"]; the backend
persists them (skipping node="execute", which the tool endpoints already log).
"""

from datetime import datetime, timezone

from . import ev, tools
from .guardrails import check_action

MAX_GUARD_REDECIDES = 2  # spec §6: on veto, re-decide at most twice, then close


def _entry(node, *, inputs_seen=None, action=None, reasoning=None, ev_score=None,
           blocked=False, block_reason=None, outcome=None, attempt_number=None):
    return {
        "node": node,
        "inputs_seen": inputs_seen,
        "action_chosen": action,
        "reasoning": reasoning,
        "ev_score": ev_score,
        "blocked": blocked,
        "block_reason": block_reason,
        "outcome": outcome,
        "attempt_number": attempt_number,
    }


def _now(state) -> datetime:
    if state.get("now_iso"):
        return datetime.fromisoformat(state["now_iso"])
    return datetime.now(timezone.utc)


# ----------------------------------------------------------------- diagnose
def diagnose(state):
    diagnosis = ev.diagnose(state["error_reason"])
    return {
        "diagnosis": diagnosis,
        "status": "IN_PROGRESS",
        "decide_loops": 0,
        "guard_vetoes": 0,
        "vetoed_actions": state.get("vetoed_actions", []),
        "trace": [_entry("diagnose",
                         inputs_seen={"error_reason": state["error_reason"]},
                         reasoning=f"deterministic map: {state['error_reason']} -> {diagnosis}",
                         outcome=diagnosis)],
    }


# ------------------------------------------------------------------- decide
def decide(state, config):
    policy = config["configurable"]["policy"]
    stats = ev.stats_from_wire(config["configurable"].get("ev_stats"))
    llm = config["configurable"].get("llm")
    loops = state.get("decide_loops", 0) + 1
    ranked = ev.rank_actions(state["diagnosis"], state["amount_paise"],
                             state.get("contacts_made", 0),
                             excluded=state.get("vetoed_actions", []),
                             stats=stats)
    inputs = {
        "diagnosis": state["diagnosis"],
        "amount_paise": state["amount_paise"],
        "attempts": state.get("attempts", 0),
        "contacts_made": state.get("contacts_made", 0),
        "vetoed_actions": state.get("vetoed_actions", []),
        "ranked_actions": ranked[:3],
        "decide_loop": loops,
        "learned_stats": stats is not None,
    }

    if not ranked:
        return {"decide_loops": loops, "ranked_actions": [],
                "chosen_action": "close_case",
                "choice_reason": "no viable actions remain",
                "trace": [_entry("decide", inputs_seen=inputs, action="close_case",
                                 reasoning="no viable actions remain")]}

    top = ranked[0]
    if top["ev"] < policy["min_ev_threshold_paise"]:
        reason = (f"abandoned: EV below threshold "
                  f"(best {top['action']} EV {top['ev']:.0f} < "
                  f"{policy['min_ev_threshold_paise']} paise)")
        return {"decide_loops": loops, "ranked_actions": ranked,
                "chosen_action": "close_case", "choice_reason": reason,
                "trace": [_entry("decide", inputs_seen=inputs, action="close_case",
                                 reasoning=reason, ev_score=top["ev"])]}

    # abandonment and no-viable-action closes above stay rule-based (governance);
    # among viable actions, the LLM (when configured) makes the final pick.
    if llm is not None and llm.available:
        candidates = [r["action"] for r in ranked]
        context = dict(inputs)
        context["ranked_actions"] = ranked  # full list, with p and EV, for the model
        action, reason, mode = llm.choose(context, candidates)
        chosen = next(r for r in ranked if r["action"] == action)
        inputs["decide_mode"] = mode
        return {"decide_loops": loops, "ranked_actions": ranked,
                "chosen_action": action, "choice_reason": reason,
                "trace": [_entry("decide", inputs_seen=inputs, action=action,
                                 reasoning=f"[{mode}] {reason}", ev_score=chosen["ev"])]}

    top = ranked[0]
    reason = f"rule-based: highest EV among {len(ranked)} viable actions"
    return {"decide_loops": loops, "ranked_actions": ranked,
            "chosen_action": top["action"], "choice_reason": reason,
            "trace": [_entry("decide", inputs_seen=inputs, action=top["action"],
                             reasoning=reason, ev_score=top["ev"])]}


# -------------------------------------------------------------------- guard
def guard(state, config):
    policy = config["configurable"]["policy"]
    action = state["chosen_action"]
    now = _now(state)
    approved = state.get("approved", False)

    verdict = check_action(action,
                           amount_paise=state["amount_paise"],
                           attempts=state.get("attempts", 0),
                           contacts_made=state.get("contacts_made", 0),
                           opted_out=state.get("opted_out", False),
                           decide_loops=state.get("decide_loops", 0),
                           approved=approved, policy=policy, now=now)

    updates = {"trace": []}

    if verdict.needs_approval:
        if state.get("auto_approve"):
            updates["approved"] = True
            updates["escalated"] = True
            updates["trace"].append(_entry(
                "guard", action=action,
                reasoning="high-value case: escalation raised and auto-approved (batch mode)",
                outcome="APPROVED"))
            # re-check the remaining rules now that approval is granted
            verdict = check_action(action,
                                   amount_paise=state["amount_paise"],
                                   attempts=state.get("attempts", 0),
                                   contacts_made=state.get("contacts_made", 0),
                                   opted_out=state.get("opted_out", False),
                                   decide_loops=state.get("decide_loops", 0),
                                   approved=True, policy=policy, now=now)
        else:
            # live mode: park the case for a human and pause the graph (Phase 5).
            updates["escalated"] = True
            updates["guard_route"] = "human_review"
            updates["trace"].append(_entry(
                "guard", action=action, blocked=True, block_reason=verdict.reason,
                reasoning="pausing for human approval", outcome="NEEDS_APPROVAL"))
            return updates

    if verdict.allowed:
        updates["guard_route"] = "close" if state["chosen_action"] == "close_case" else "execute"
        if state["chosen_action"] == "close_case":
            updates["close_reason"] = state.get("choice_reason", "")
        updates["trace"].append(_entry("guard", action=state["chosen_action"],
                                       reasoning="all policy checks passed", outcome="ALLOWED"))
        return updates

    if verdict.hard_stop:
        updates["guard_route"] = "close"
        updates["close_reason"] = verdict.reason
        updates["trace"].append(_entry("guard", action=action, blocked=True,
                                       block_reason=verdict.reason, outcome="HARD_STOP"))
        return updates

    # plain veto: remove the action, re-decide (bounded)
    vetoes = state.get("guard_vetoes", 0) + 1
    updates["guard_vetoes"] = vetoes
    updates["vetoed_actions"] = state.get("vetoed_actions", []) + [action]
    updates["trace"].append(_entry("guard", action=action, blocked=True,
                                   block_reason=verdict.reason, outcome="VETO"))
    if vetoes > MAX_GUARD_REDECIDES:
        updates["guard_route"] = "close"
        updates["close_reason"] = f"closed after {vetoes} guard vetoes (last: {verdict.reason})"
    else:
        updates["guard_route"] = "decide"
    return updates


# ------------------------------------------------------------------ execute
def execute(state):
    action = state["chosen_action"]
    try:
        result = tools.execute_action(action, state["case_id"])
    except Exception as e:  # tool/backend failure: fail safe, close the case
        return {"status": "TOOL_ERROR",
                "close_reason": f"tool error on {action}: {e}",
                "trace": [_entry("execute", action=action, outcome="ERROR",
                                 reasoning=str(e))]}

    outcome = result.get("outcome", "FAILED")
    updates = {
        "attempts": result.get("attempts", state.get("attempts", 0)),
        "contacts_made": result.get("contacts_made", state.get("contacts_made", 0)),
        "status": result.get("status", state.get("status")),
        "recovered_paise": result.get("recovered_paise", 0),
        "actions": [action],
        "last_outcome": outcome,
        "trace": [_entry("execute", action=action, outcome=outcome,
                         attempt_number=result.get("attempts"))],
    }
    return updates


# ------------------------------------------------------------- check_outcome
def check_outcome(state):
    outcome = state.get("last_outcome", "FAILED")
    status = state.get("status", "IN_PROGRESS")

    if status in ("RECOVERED", "ESCALATED", "SCHEDULED", "CLOSED", "TOOL_ERROR"):
        route = "close"
    elif outcome == "PENDING":
        route = "close"   # live mode: action initiated, outcome arrives via webhook
    elif outcome == "FAILED":
        route = "decide"
    else:
        route = "close"

    updates = {"outcome_route": route,
               "trace": [_entry("check_outcome", outcome=outcome,
                                reasoning=f"status={status} -> {route}")]}
    if outcome == "FAILED" and route == "decide":
        # deterministic policy: never repeat an action that just failed
        updates["vetoed_actions"] = (state.get("vetoed_actions", [])
                                     + [state["chosen_action"]])
    return updates


# ------------------------------------------------- escalate_notify (Phase 5)
def escalate_notify(state):
    """Marks the case WAITING_APPROVAL in the backend via the escalate tool.
    Kept separate from human_review so the tool call is NOT re-executed when
    the graph resumes from the interrupt (a resumed node restarts from its top)."""
    reason = (f"amount ₹{state['amount_paise'] / 100:,.0f} exceeds auto-approval limit; "
              "human approval required")
    try:
        result = tools.escalate(state["case_id"], reason)
        status = result.get("status", "WAITING_APPROVAL")
    except Exception as e:
        status = state.get("status", "IN_PROGRESS")
        reason = f"{reason} (escalate tool failed: {e})"
    return {"status": status,
            "trace": [_entry("execute", action="escalate", reasoning=reason,
                             outcome=status)]}


# ----------------------------------------------------- human_review (Phase 5)
def human_review(state):
    """Pauses here (LangGraph interrupt) until POST /resume delivers the human's
    decision. The pause lives in the PostgresSaver checkpoint, so it survives
    an agent restart."""
    from langgraph.types import interrupt

    approved = interrupt({
        "case_id": state["case_id"],
        "amount_paise": state["amount_paise"],
        "diagnosis": state.get("diagnosis"),
        "question": "Approve recovery actions for this high-value case?",
    })

    if approved:
        return {"approved": True, "status": "IN_PROGRESS", "human_route": "decide",
                "trace": [_entry("human_review", outcome="APPROVED",
                                 reasoning="human approved escalation; resuming decisions")]}
    return {"status": "ESCALATED", "human_route": "close",
            "close_reason": "escalation rejected by human",
            "trace": [_entry("human_review", outcome="REJECTED",
                             reasoning="human rejected escalation; stopping")]}


# -------------------------------------------------------------------- close
def close(state):
    status = state.get("status", "IN_PROGRESS")
    if status in ("RECOVERED", "ESCALATED", "SCHEDULED"):
        return {"trace": [_entry("close", outcome=status,
                                 reasoning="terminal state reached, nothing to close")]}
    if state.get("last_outcome") == "PENDING":
        # live mode: a retry order / payment link is out there; the case stays
        # open and the payment webhook will settle it. Do NOT close.
        return {"trace": [_entry("close", outcome="PENDING",
                                 reasoning="live action initiated; awaiting webhook outcome")]}

    reason = state.get("close_reason") or "no recovery path found"
    try:
        tools.close_case(state["case_id"], reason)
    except Exception as e:
        return {"status": "CLOSED", "close_reason": reason,
                "trace": [_entry("close", action="close_case", outcome="ERROR",
                                 reasoning=f"{reason} (close tool failed: {e})")]}
    return {"status": "CLOSED", "close_reason": reason,
            "trace": [_entry("close", action="close_case", outcome="CLOSED",
                             reasoning=reason)]}


# routing helpers used by build.py
def route_from_guard(state):
    return state["guard_route"]


def route_from_outcome(state):
    return state["outcome_route"]


def route_from_human(state):
    return state["human_route"]
