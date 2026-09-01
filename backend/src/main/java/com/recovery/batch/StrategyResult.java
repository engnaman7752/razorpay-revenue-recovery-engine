package com.recovery.batch;

import java.util.LinkedHashMap;
import java.util.Map;

/** Metrics for one strategy over the 300-case batch. */
public class StrategyResult {

    public final String strategy;
    public long recoveredPaise;
    public int casesRecovered;
    public int contactsMade;
    public int paymentAttempts;
    public int actionsTaken;
    public int stoppingRuleActivations;   // agent-only; 0 for baselines
    public int escalations;               // agent-only; 0 for baselines
    public java.util.List<Map<String, Object>> learningCurve;   // agent-only, Phase 4
    public Map<String, Map<String, Object>> perCause;           // agent-only, Phase 4

    public StrategyResult(String strategy) {
        this.strategy = strategy;
    }

    public double contactsPer10kRecovered() {
        if (recoveredPaise == 0) {
            return 0.0;
        }
        // ₹10,000 = 1,000,000 paise
        return contactsMade / (recoveredPaise / 1_000_000.0);
    }

    public Map<String, Object> toMetricsMap(long oracleRecoveredPaise, long totalAtRiskPaise) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("recovered_paise", recoveredPaise);
        m.put("pct_of_oracle", oracleRecoveredPaise == 0 ? 0.0
                : Math.round(1000.0 * recoveredPaise / oracleRecoveredPaise) / 10.0);
        m.put("cases_recovered", casesRecovered);
        m.put("contacts_made", contactsMade);
        m.put("contacts_per_10k_recovered",
                Math.round(contactsPer10kRecovered() * 100.0) / 100.0);
        m.put("payment_attempts", paymentAttempts);
        m.put("actions_taken", actionsTaken);
        m.put("stopping_rule_activations", stoppingRuleActivations);
        m.put("escalations", escalations);
        m.put("total_at_risk_paise", totalAtRiskPaise);
        if (learningCurve != null) {
            m.put("learning_curve", learningCurve);
        }
        if (perCause != null) {
            m.put("per_cause", perCause);
        }
        return m;
    }
}
