package com.recovery.razorpay;

/**
 * The payment-affecting actions the system can take on a case.
 * (escalate / close are workflow actions, not gateway actions, and live elsewhere.)
 * Wire names match ground_truth.recovers_if in data/cases.jsonl and the agent's action names.
 */
public enum RecoveryAction {
    RETRY_NOW("retry_now", false),
    SCHEDULE_RETRY_24H("schedule_retry_24h", false),
    PAYMENT_LINK("payment_link", true),
    REMINDER_WITH_LINK("reminder_with_link", true);

    private final String wire;
    private final boolean customerContact;

    RecoveryAction(String wire, boolean customerContact) {
        this.wire = wire;
        this.customerContact = customerContact;
    }

    public String wire() {
        return wire;
    }

    /** true if this action reaches out to the customer (counts against contact limits / opt-out). */
    public boolean isCustomerContact() {
        return customerContact;
    }

    public static RecoveryAction fromWire(String wire) {
        for (RecoveryAction a : values()) {
            if (a.wire.equals(wire)) {
                return a;
            }
        }
        throw new IllegalArgumentException("Unknown action: " + wire);
    }
}
