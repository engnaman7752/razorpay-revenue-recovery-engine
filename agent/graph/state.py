"""Graph state. Deliberately small (<5KB): ids, short strings, ints only."""

import operator
from typing import Annotated, TypedDict


class RecoveryState(TypedDict, total=False):
    # case snapshot (input)
    case_id: str
    amount_paise: int
    error_reason: str
    opted_out: bool
    attempts: int
    contacts_made: int

    # run controls
    auto_approve: bool       # batch mode: a human approver is simulated
    now_iso: str             # injected clock (determinism in batch/tests); "" = real now

    # working state
    diagnosis: str
    ranked_actions: list     # [{action, p, ev}] from ev.rank_actions
    chosen_action: str
    choice_reason: str
    vetoed_actions: list     # actions removed by guard vetoes or already tried
    decide_loops: int
    guard_vetoes: int        # consecutive re-decides caused by guard, max 2
    approved: bool           # escalation approval granted (auto or human)
    escalated: bool

    # routing (set by nodes, read by conditional edges)
    guard_route: str         # execute | decide | close | human_review
    human_route: str         # decide | close (set by human_review after resume)
    outcome_route: str       # decide | close
    last_outcome: str        # RECOVERED | FAILED | SCHEDULED | ...

    # outputs
    status: str              # IN_PROGRESS | RECOVERED | ESCALATED | SCHEDULED | CLOSED
    recovered_paise: int
    close_reason: str
    actions: Annotated[list, operator.add]   # wire names of executed actions
    trace: Annotated[list, operator.add]     # decision_log entries, persisted by backend
