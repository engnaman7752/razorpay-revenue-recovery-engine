package com.recovery.tools;

import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import com.recovery.razorpay.GatewayResult;
import com.recovery.razorpay.RecoveryAction;
import org.springframework.stereotype.Service;

import java.util.Map;

/** Simulated reminder send (email/sms/whatsapp) with a payment link attached.
 * Always logged; counts as a customer contact. */
@Service
public class ReminderTool {

    private final CaseToolSupport support;
    private final DecisionLogger decisionLogger;

    public ReminderTool(CaseToolSupport support, DecisionLogger decisionLogger) {
        this.support = support;
        this.decisionLogger = decisionLogger;
    }

    public Map<String, Object> run(String caseId, String channel) {
        RecoveryCase c = support.find(caseId);
        GatewayResult result = support.resolve(c, RecoveryAction.REMINDER_WITH_LINK);
        String outcome = result.success() ? "RECOVERED" : result.pending() ? "PENDING" : "FAILED";
        decisionLogger.logAction(c.getId(), RecoveryAction.REMINDER_WITH_LINK.wire(),
                "reminder via " + channel + ": " + result.detail(), outcome, null);
        return support.respond(c, outcome);
    }
}
