"""Cause taxonomy, Beta-Bernoulli priors, and expected-value ranking.

EV(action) = P(recovery | cause, action) * amount_paise
             - contact_penalty(contacts_made)
             - fixed_action_cost

P comes from a Beta(alpha, beta) posterior mean. Phase 3 uses the priors
below; Phase 4 updates alpha/beta from observed outcomes (ev_stats table).
All money values are paise.
"""

# --- deterministic diagnosis: Razorpay error reason -> cause (NOT the LLM) ---
CAUSE_MAP = {
    "insufficient_fund": "SOFT_DECLINE",
    "gateway_technical_error": "TRANSIENT",
    "payment_timed_out": "TRANSIENT",
    "card_declined": "HARD_DECLINE",
    "card_disabled_for_online_payments": "HARD_DECLINE",
    "authentication_failed": "CUSTOMER_ACTION",
    "payment_cancelled": "CUSTOMER_ACTION",
    "card_number_invalid": "UNRECOVERABLE",

    # --- Real Razorpay webhook error_reason values (live mode) -------------
    # Razorpay's live payment.failed events use different, often generic
    # strings than the synthetic dataset above. Map the ones test mode emits
    # so a real failed payment diagnoses cleanly instead of falling through to
    # UNRECOVERABLE. A generic "payment_failed" is treated as TRANSIENT — the
    # safe, cheap first move is a retry, and if that fails the graph escalates
    # to a link on its own.
    "payment_failed": "TRANSIENT",
    "gateway_error": "TRANSIENT",
    "server_error": "TRANSIENT",
    "payment_timed_out_error": "TRANSIENT",
    "payment_pending": "TRANSIENT",
    "insufficient_funds": "SOFT_DECLINE",
    "payment_declined_by_bank": "SOFT_DECLINE",
    "card_expired": "HARD_DECLINE",
    "international_transaction_not_allowed": "HARD_DECLINE",
    "card_not_supported": "HARD_DECLINE",
    "payment_canceled_by_user": "CUSTOMER_ACTION",
    "payment_cancelled_by_user": "CUSTOMER_ACTION",
    "invalid_card": "UNRECOVERABLE",
}

ACTIONS = ["retry_now", "schedule_retry_24h", "payment_link", "reminder_with_link"]
CONTACT_ACTIONS = {"payment_link", "reminder_with_link"}
RETRY_ACTIONS = {"retry_now", "schedule_retry_24h"}

# --- priors as (alpha, beta) counts; posterior mean = alpha / (alpha + beta) ---
# Spec-pinned values: TRANSIENT+retry_now 0.75, SOFT_DECLINE+schedule 0.55,
# SOFT_DECLINE+retry_now 0.15, HARD_DECLINE+payment_link 0.40,
# HARD_DECLINE+retry 0.02, CUSTOMER_ACTION+reminder_with_link 0.35.
PRIORS = {
    ("SOFT_DECLINE", "schedule_retry_24h"): (11, 9),    # 0.55
    ("SOFT_DECLINE", "retry_now"): (3, 17),             # 0.15
    ("SOFT_DECLINE", "payment_link"): (4, 16),          # 0.20
    ("SOFT_DECLINE", "reminder_with_link"): (2, 18),    # 0.10

    ("TRANSIENT", "retry_now"): (15, 5),                # 0.75
    ("TRANSIENT", "schedule_retry_24h"): (6, 14),       # 0.30
    ("TRANSIENT", "payment_link"): (2, 18),             # 0.10
    ("TRANSIENT", "reminder_with_link"): (1, 19),       # 0.05

    ("HARD_DECLINE", "payment_link"): (8, 12),          # 0.40
    ("HARD_DECLINE", "reminder_with_link"): (4, 16),    # 0.20
    ("HARD_DECLINE", "retry_now"): (1, 49),             # 0.02
    ("HARD_DECLINE", "schedule_retry_24h"): (1, 49),    # 0.02

    ("CUSTOMER_ACTION", "reminder_with_link"): (7, 13), # 0.35
    ("CUSTOMER_ACTION", "payment_link"): (5, 15),       # 0.25
    ("CUSTOMER_ACTION", "retry_now"): (2, 18),          # 0.10
    ("CUSTOMER_ACTION", "schedule_retry_24h"): (2, 18), # 0.10

    ("UNRECOVERABLE", "payment_link"): (2, 18),         # 0.10 (new payment method)
    ("UNRECOVERABLE", "reminder_with_link"): (1, 19),   # 0.05
    ("UNRECOVERABLE", "retry_now"): (1, 49),            # 0.02
    ("UNRECOVERABLE", "schedule_retry_24h"): (1, 49),   # 0.02
}

# fixed operational cost per action, paise
FIXED_ACTION_COST = {
    "retry_now": 500,            # ₹5  gateway fee
    "schedule_retry_24h": 700,   # ₹7  gateway fee + delay cost
    "payment_link": 1500,        # ₹15 link + message
    "reminder_with_link": 1200,  # ₹12 message
}

# each additional customer contact gets more annoying: ₹20 per prior contact
CONTACT_PENALTY_PER_PRIOR_CONTACT = 2000


def diagnose(error_reason: str) -> str:
    return CAUSE_MAP.get(error_reason, "UNRECOVERABLE")


def stats_from_wire(wire: dict | None) -> dict | None:
    """Convert the backend's ev_stats payload
    {"SOFT_DECLINE": {"retry_now": [3, 17], ...}, ...}
    into the {(cause, action): (alpha, beta)} shape used here."""
    if not wire:
        return None
    return {(cause, action): tuple(ab)
            for cause, actions in wire.items()
            for action, ab in actions.items()}


def probability(cause: str, action: str, stats: dict | None = None) -> float:
    """Posterior mean. `stats` (Phase 4) overrides priors with learned counts:
    {(cause, action): (alpha, beta)}."""
    table = stats if stats and (cause, action) in stats else PRIORS
    alpha, beta = table.get((cause, action), (1, 49))
    return alpha / (alpha + beta)


def expected_value(cause: str, action: str, amount_paise: int,
                   contacts_made: int, stats: dict | None = None) -> float:
    p = probability(cause, action, stats)
    penalty = (CONTACT_PENALTY_PER_PRIOR_CONTACT * contacts_made
               if action in CONTACT_ACTIONS else 0)
    return p * amount_paise - penalty - FIXED_ACTION_COST[action]


def rank_actions(cause: str, amount_paise: int, contacts_made: int,
                 excluded: list | None = None, stats: dict | None = None) -> list:
    """All non-excluded actions, highest EV first."""
    excluded = set(excluded or [])
    ranked = []
    for action in ACTIONS:
        if action in excluded:
            continue
        ranked.append({
            "action": action,
            "p": round(probability(cause, action, stats), 3),
            "ev": round(expected_value(cause, action, amount_paise, contacts_made, stats), 1),
        })
    ranked.sort(key=lambda r: r["ev"], reverse=True)
    return ranked
