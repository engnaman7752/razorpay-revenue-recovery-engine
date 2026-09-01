package com.recovery.tools;

import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import com.recovery.razorpay.GatewayResult;
import com.recovery.razorpay.RecoveryAction;
import org.springframework.stereotype.Service;

import java.util.Map;

/** Sends the customer a Razorpay Payment Link (live: Payment Links API, Phase 6;
 * simulated: gateway resolves whether the customer pays). Counts as a contact. */
@Service
public class PaymentLinkTool {

    private final CaseToolSupport support;
    private final DecisionLogger decisionLogger;

    public PaymentLinkTool(CaseToolSupport support, DecisionLogger decisionLogger) {
        this.support = support;
        this.decisionLogger = decisionLogger;
    }

    public Map<String, Object> run(String caseId) {
        RecoveryCase c = support.find(caseId);
        GatewayResult result = support.resolve(c, RecoveryAction.PAYMENT_LINK);
        String outcome = result.success() ? "RECOVERED" : result.pending() ? "PENDING" : "FAILED";
        decisionLogger.logAction(c.getId(), RecoveryAction.PAYMENT_LINK.wire(),
                result.detail(), outcome, null);
        return support.respond(c, outcome);
    }
}
