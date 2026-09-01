"""Policy-as-code guard rules. Pure functions only — no I/O, no clock reads,
no network. Everything takes its inputs (policy dict, now) as arguments so it
is trivially unit-testable. The guard node enforces these; prompts never do.
"""

from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from .ev import CONTACT_ACTIONS, RETRY_ACTIONS


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    hard_stop: bool = False       # stop the whole case, don't re-decide
    needs_approval: bool = False  # high-value case: require human approval first
    reason: str = ""


def in_quiet_hours(now: datetime, policy: dict) -> bool:
    """True if `now` falls inside the configured quiet window (may cross midnight)."""
    qh = policy["quiet_hours"]
    tz = ZoneInfo(qh.get("tz", "Asia/Kolkata"))
    local = now.astimezone(tz).time()
    start = time.fromisoformat(qh["start"])
    end = time.fromisoformat(qh["end"])
    if start <= end:
        return start <= local < end
    return local >= start or local < end   # window crosses midnight


def check_action(action: str, *, amount_paise: int, attempts: int, contacts_made: int,
                 opted_out: bool, decide_loops: int, approved: bool,
                 policy: dict, now: datetime) -> Verdict:
    """Decide whether one proposed action may run. Order matters:
    hard stops first, then approval, then per-action vetoes."""

    if opted_out and action != "close_case":
        return Verdict(False, hard_stop=True,
                       reason="customer opted out: immediate stop (policy opt_out)")

    if decide_loops > policy["max_decide_loops"]:
        return Verdict(False, hard_stop=True,
                       reason=f"max_decide_loops ({policy['max_decide_loops']}) exhausted")

    if action == "close_case":
        return Verdict(True)

    if amount_paise > policy["auto_escalate_above_inr"] * 100 and not approved:
        return Verdict(False, needs_approval=True,
                       reason=f"amount above ₹{policy['auto_escalate_above_inr']:,}: "
                              "human approval required before any action")

    if action in RETRY_ACTIONS and attempts >= policy["max_payment_attempts"]:
        return Verdict(False,
                       reason=f"max_payment_attempts ({policy['max_payment_attempts']}) reached")

    if action in CONTACT_ACTIONS and contacts_made >= policy["max_customer_contacts"]:
        return Verdict(False,
                       reason=f"max_customer_contacts ({policy['max_customer_contacts']}) reached")

    if action in CONTACT_ACTIONS and in_quiet_hours(now, policy):
        return Verdict(False, reason="quiet hours: no customer contact between "
                                     f"{policy['quiet_hours']['start']} and "
                                     f"{policy['quiet_hours']['end']}")

    return Verdict(True)
