"""Unit tests for the pure guard functions and the EV table.
These run with no network, no database, no clock — everything injected."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from graph import ev
from graph.guardrails import check_action, in_quiet_hours

POLICY = {
    "max_payment_attempts": 3,
    "max_customer_contacts": 2,
    "max_decide_loops": 4,
    "quiet_hours": {"start": "21:00", "end": "08:00", "tz": "Asia/Kolkata"},
    "auto_escalate_above_inr": 25000,
    "min_ev_threshold_paise": 5000,
    "opt_out": "immediate_stop",
}

IST = ZoneInfo("Asia/Kolkata")
DAY = datetime(2026, 8, 27, 12, 0, tzinfo=IST)     # 12:00 IST
NIGHT = datetime(2026, 8, 27, 22, 30, tzinfo=IST)  # 22:30 IST
EARLY = datetime(2026, 8, 27, 6, 0, tzinfo=IST)    # 06:00 IST


def _check(action, **overrides):
    kwargs = dict(amount_paise=500_00, attempts=0, contacts_made=0, opted_out=False,
                  decide_loops=1, approved=False, policy=POLICY, now=DAY)
    kwargs.update(overrides)
    return check_action(action, **kwargs)


# ---------------------------------------------------------------- quiet hours
def test_quiet_hours_inside_evening():
    assert in_quiet_hours(NIGHT, POLICY)


def test_quiet_hours_inside_early_morning():
    assert in_quiet_hours(EARLY, POLICY)  # window crosses midnight


def test_quiet_hours_outside():
    assert not in_quiet_hours(DAY, POLICY)


def test_quiet_hours_respects_timezone():
    # 23:00 UTC == 04:30 IST -> inside quiet hours
    utc_night = datetime(2026, 8, 27, 23, 0, tzinfo=ZoneInfo("UTC"))
    assert in_quiet_hours(utc_night, POLICY)


def test_contact_blocked_in_quiet_hours_but_retry_allowed():
    assert not _check("reminder_with_link", now=NIGHT).allowed
    assert _check("retry_now", now=NIGHT).allowed  # retries don't wake anyone


# ------------------------------------------------------------------- opt-out
def test_opt_out_is_hard_stop_for_any_action():
    for action in ["retry_now", "payment_link", "reminder_with_link", "schedule_retry_24h"]:
        v = _check(action, opted_out=True)
        assert not v.allowed and v.hard_stop


def test_opt_out_still_allows_closing():
    assert _check("close_case", opted_out=True).allowed


# -------------------------------------------------------------------- limits
def test_attempts_cap_blocks_retries():
    v = _check("retry_now", attempts=3)
    assert not v.allowed and not v.hard_stop  # veto, not stop: other actions may work


def test_attempts_cap_does_not_block_contact():
    assert _check("payment_link", attempts=3).allowed


def test_contact_cap_blocks_contact_actions():
    v = _check("reminder_with_link", contacts_made=2)
    assert not v.allowed


def test_decide_loop_exhaustion_is_hard_stop():
    v = _check("retry_now", decide_loops=5)
    assert not v.allowed and v.hard_stop


# ---------------------------------------------------------------- escalation
def test_high_value_needs_approval():
    v = _check("retry_now", amount_paise=30_000_00)
    assert not v.allowed and v.needs_approval


def test_high_value_allowed_after_approval():
    assert _check("retry_now", amount_paise=30_000_00, approved=True).allowed


def test_threshold_is_exclusive():
    assert _check("retry_now", amount_paise=25_000_00).allowed  # exactly ₹25k: no approval


# ------------------------------------------------------------------ EV table
def test_diagnosis_map_matches_spec():
    assert ev.diagnose("insufficient_fund") == "SOFT_DECLINE"
    assert ev.diagnose("gateway_technical_error") == "TRANSIENT"
    assert ev.diagnose("payment_timed_out") == "TRANSIENT"
    assert ev.diagnose("card_declined") == "HARD_DECLINE"
    assert ev.diagnose("card_disabled_for_online_payments") == "HARD_DECLINE"
    assert ev.diagnose("authentication_failed") == "CUSTOMER_ACTION"
    assert ev.diagnose("payment_cancelled") == "CUSTOMER_ACTION"
    assert ev.diagnose("card_number_invalid") == "UNRECOVERABLE"
    assert ev.diagnose("something_new") == "UNRECOVERABLE"  # unknown fails safe


def test_spec_pinned_priors():
    assert ev.probability("TRANSIENT", "retry_now") == pytest.approx(0.75)
    assert ev.probability("SOFT_DECLINE", "schedule_retry_24h") == pytest.approx(0.55)
    assert ev.probability("SOFT_DECLINE", "retry_now") == pytest.approx(0.15)
    assert ev.probability("HARD_DECLINE", "payment_link") == pytest.approx(0.40)
    assert ev.probability("HARD_DECLINE", "retry_now") == pytest.approx(0.02)
    assert ev.probability("CUSTOMER_ACTION", "reminder_with_link") == pytest.approx(0.35)


def test_ranking_prefers_right_action_per_cause():
    assert ev.rank_actions("TRANSIENT", 200000, 0)[0]["action"] == "retry_now"
    assert ev.rank_actions("SOFT_DECLINE", 200000, 0)[0]["action"] == "schedule_retry_24h"
    assert ev.rank_actions("HARD_DECLINE", 200000, 0)[0]["action"] == "payment_link"
    assert ev.rank_actions("CUSTOMER_ACTION", 200000, 0)[0]["action"] == "reminder_with_link"


def test_excluded_actions_are_not_ranked():
    ranked = ev.rank_actions("SOFT_DECLINE", 200000, 0, excluded=["schedule_retry_24h"])
    assert all(r["action"] != "schedule_retry_24h" for r in ranked)


def test_contact_penalty_grows_with_contacts():
    ev0 = ev.expected_value("HARD_DECLINE", "payment_link", 200000, 0)
    ev1 = ev.expected_value("HARD_DECLINE", "payment_link", 200000, 1)
    assert ev1 == ev0 - ev.CONTACT_PENALTY_PER_PRIOR_CONTACT


def test_tiny_case_falls_below_ev_threshold():
    # ₹200 UNRECOVERABLE case: best EV must be under the ₹50 threshold -> abandon
    best = ev.rank_actions("UNRECOVERABLE", 20000, 0)[0]
    assert best["ev"] < POLICY["min_ev_threshold_paise"]
