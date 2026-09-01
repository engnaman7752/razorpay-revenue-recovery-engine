"""Synthetic failed-payment case generator (Razorpay Recovery Engine).

Writes data/cases.jsonl: 300 cases, seeded RNG (seed=42), distribution per spec §9.

ground_truth.recovers_if is the single action that would recover the payment
(or null if the case is unrecoverable). Draw probabilities are chosen to be
consistent with the priors in agent EV table, so ORACLE > AGENT > NAIVE is
achievable but not rigged.
"""

import json
import math
import random
import uuid
from collections import Counter
from pathlib import Path

SEED = 42
N_CASES = 300
OUT_PATH = Path(__file__).parent / "cases.jsonl"

# --- §9 error-reason mix (exact counts for reproducibility; sums to 300) ---
ERROR_MIX = [
    ("insufficient_fund", 105),                    # 35%
    ("gateway_technical_error", 30),               # 20% split with next
    ("payment_timed_out", 30),
    ("card_declined", 23),                         # 15% split with next
    ("card_disabled_for_online_payments", 22),
    ("authentication_failed", 30),                 # 10%
    ("payment_cancelled", 30),                     # 10%
    ("card_number_invalid", 30),                   # 10%
]

ERROR_SOURCE = {
    "insufficient_fund": "customer",
    "gateway_technical_error": "gateway",
    "payment_timed_out": "gateway",
    "card_declined": "issuer_bank",
    "card_disabled_for_online_payments": "issuer_bank",
    "authentication_failed": "customer",
    "payment_cancelled": "customer",
    "card_number_invalid": "customer",
}

# --- ground truth: (action, probability) per error reason; remainder = unrecoverable.
# Kept consistent with the agent's priors (§5) without matching them exactly.
GROUND_TRUTH_DIST = {
    "insufficient_fund": [("schedule_retry_24h", 0.55), ("retry_now", 0.12), ("payment_link", 0.03)],
    "gateway_technical_error": [("retry_now", 0.75), ("schedule_retry_24h", 0.05)],
    "payment_timed_out": [("retry_now", 0.75), ("schedule_retry_24h", 0.05)],
    "card_declined": [("payment_link", 0.40), ("retry_now", 0.02)],
    "card_disabled_for_online_payments": [("payment_link", 0.40), ("retry_now", 0.02)],
    "authentication_failed": [("reminder_with_link", 0.35), ("payment_link", 0.15)],
    "payment_cancelled": [("reminder_with_link", 0.35), ("payment_link", 0.15)],
    "card_number_invalid": [("payment_link", 0.10)],  # only a new payment method can save it
}

# --- amount model: log-normal over rupees, clipped to ₹200–₹80,000, ~8% above ₹25,000
AMOUNT_MU = math.log(2500)   # median ≈ ₹2,500
AMOUNT_SIGMA = 1.64
MIN_RUPEES, MAX_RUPEES = 200, 80_000
ESCALATION_RUPEES = 25_000


def draw_amount_paise(rng: random.Random) -> int:
    rupees = rng.lognormvariate(AMOUNT_MU, AMOUNT_SIGMA)
    rupees = max(MIN_RUPEES, min(MAX_RUPEES, rupees))
    return int(round(rupees * 100))


def draw_ground_truth(rng: random.Random, error_reason: str) -> dict:
    roll = rng.random()
    cum = 0.0
    for action, p in GROUND_TRUTH_DIST[error_reason]:
        cum += p
        if roll < cum:
            return {"recoverable": True, "recovers_if": action}
    return {"recoverable": False, "recovers_if": None}


def draw_customer_history(rng: random.Random) -> dict:
    return {
        "past_success": rng.randint(0, 20),
        "past_failures": rng.randint(0, 5),
        "opted_out": False,  # set separately for exactly 2% of cases
    }


def main() -> None:
    rng = random.Random(SEED)

    reasons = [r for r, n in ERROR_MIX for _ in range(n)]
    rng.shuffle(reasons)

    cases = []
    for i, reason in enumerate(reasons):
        case_uuid = str(uuid.UUID(int=rng.getrandbits(128), version=4))
        cases.append({
            "id": case_uuid,
            "razorpay_order_id": f"order_SYN{i:05d}",
            "razorpay_payment_id": f"pay_SYN{i:05d}",
            "amount_paise": draw_amount_paise(rng),
            "currency": "INR",
            "error_reason": reason,
            "error_source": ERROR_SOURCE[reason],
            "customer_id": f"cust_{rng.randint(1, 120):04d}",
            "customer_history": draw_customer_history(rng),
            "source": "SYNTHETIC",
            "ground_truth": draw_ground_truth(rng, reason),
        })

    # exactly 2% opted out (6 cases)
    for idx in rng.sample(range(N_CASES), k=int(N_CASES * 0.02)):
        cases[idx]["customer_history"]["opted_out"] = True

    with OUT_PATH.open("w") as f:
        for case in cases:
            f.write(json.dumps(case) + "\n")

    # --- verification printout ---
    reason_counts = Counter(c["error_reason"] for c in cases)
    n_above = sum(c["amount_paise"] > ESCALATION_RUPEES * 100 for c in cases)
    n_opted_out = sum(c["customer_history"]["opted_out"] for c in cases)
    n_recoverable = sum(c["ground_truth"]["recoverable"] for c in cases)
    recovers_if_counts = Counter(
        c["ground_truth"]["recovers_if"] for c in cases if c["ground_truth"]["recoverable"]
    )
    amounts = sorted(c["amount_paise"] for c in cases)

    print(f"wrote {len(cases)} cases -> {OUT_PATH}")
    print("\nerror_reason distribution:")
    for reason, _ in ERROR_MIX:
        n = reason_counts[reason]
        print(f"  {reason:<35} {n:>4}  ({n / N_CASES:.1%})")
    print(f"\namount range: ₹{amounts[0] / 100:,.0f} – ₹{amounts[-1] / 100:,.0f}"
          f"   median ₹{amounts[N_CASES // 2] / 100:,.0f}")
    print(f"above ₹{ESCALATION_RUPEES:,}: {n_above} cases ({n_above / N_CASES:.1%}, target ~8%)")
    print(f"opted_out: {n_opted_out} cases ({n_opted_out / N_CASES:.1%}, target 2%)")
    print(f"recoverable: {n_recoverable}/{N_CASES} ({n_recoverable / N_CASES:.1%})")
    print("recovers_if breakdown:", dict(recovers_if_counts))
    total_at_risk = sum(c["amount_paise"] for c in cases)
    total_recoverable = sum(c["amount_paise"] for c in cases if c["ground_truth"]["recoverable"])
    print(f"total at risk: ₹{total_at_risk / 100:,.0f}   "
          f"oracle-recoverable: ₹{total_recoverable / 100:,.0f}")


if __name__ == "__main__":
    main()
