package com.recovery.tools;

import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import com.recovery.razorpay.GatewayResult;
import com.recovery.razorpay.RecoveryAction;
import org.springframework.stereotype.Service;

import java.util.Map;

/** Immediate retry: in live mode this creates a fresh Razorpay order for the
 * same case (Phase 6); in simulated mode the gateway resolves it instantly. */
@Service
public class RetryPaymentTool {

    private final CaseToolSupport support;
    private final DecisionLogger decisionLogger;

    public RetryPaymentTool(CaseToolSupport support, DecisionLogger decisionLogger) {
        this.support = support;
        this.decisionLogger = decisionLogger;
    }

    public Map<String, Object> run(String caseId) {
        RecoveryCase c = support.find(caseId);
        GatewayResult result = support.resolve(c, RecoveryAction.RETRY_NOW);
        String outcome = result.success() ? "RECOVERED" : result.pending() ? "PENDING" : "FAILED";
        decisionLogger.logAction(c.getId(), RecoveryAction.RETRY_NOW.wire(),
                result.detail(), outcome, c.getAttempts());
        return support.respond(c, outcome);
    }
}
