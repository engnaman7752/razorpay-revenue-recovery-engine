package com.recovery.razorpay;

import java.util.Map;

/** Deterministic error-reason -> cause taxonomy.
 * Mirrors agent/graph/ev.py CAUSE_MAP — keep the two in sync. */
public final class CauseMap {

    private static final Map<String, String> MAP = Map.of(
            "insufficient_fund", "SOFT_DECLINE",
            "gateway_technical_error", "TRANSIENT",
            "payment_timed_out", "TRANSIENT",
            "card_declined", "HARD_DECLINE",
            "card_disabled_for_online_payments", "HARD_DECLINE",
            "authentication_failed", "CUSTOMER_ACTION",
            "payment_cancelled", "CUSTOMER_ACTION",
            "card_number_invalid", "UNRECOVERABLE");

    private CauseMap() {
    }

    public static String diagnose(String errorReason) {
        return MAP.getOrDefault(errorReason == null ? "" : errorReason, "UNRECOVERABLE");
    }
}
