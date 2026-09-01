package com.recovery.tools;

import com.recovery.domain.CaseStatus;
import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import org.springframework.stereotype.Service;

import java.util.Map;

/** Terminal action. Closing is always a logged decision with a reason —
 * cases are never silently dropped. */
@Service
public class CloseCaseTool {

    private final CaseToolSupport support;
    private final DecisionLogger decisionLogger;

    public CloseCaseTool(CaseToolSupport support, DecisionLogger decisionLogger) {
        this.support = support;
        this.decisionLogger = decisionLogger;
    }

    public Map<String, Object> run(String caseId, String reason) {
        RecoveryCase c = support.find(caseId);
        if (c.getStatus() != CaseStatus.RECOVERED && c.getStatus() != CaseStatus.ESCALATED) {
            c.setStatus(CaseStatus.CLOSED);
            support.save(c);
        }
        decisionLogger.log(c.getId(), "close", null, "close_case", reason,
                null, false, null, "CLOSED", null);
        return support.respond(c, "CLOSED");
    }
}
