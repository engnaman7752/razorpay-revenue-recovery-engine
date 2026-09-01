package com.recovery.tools;

import com.recovery.domain.CaseStatus;
import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import org.springframework.stereotype.Service;

import java.util.Map;

/** Parks the case in the human approval queue (status WAITING_APPROVAL).
 * A person approves or rejects it via EscalationController, which resumes
 * the agent's paused graph. */
@Service
public class EscalateTool {

    private final CaseToolSupport support;
    private final DecisionLogger decisionLogger;

    public EscalateTool(CaseToolSupport support, DecisionLogger decisionLogger) {
        this.support = support;
        this.decisionLogger = decisionLogger;
    }

    public Map<String, Object> run(String caseId, String reason) {
        RecoveryCase c = support.find(caseId);
        c.setStatus(CaseStatus.WAITING_APPROVAL);
        support.save(c);
        decisionLogger.log(c.getId(), "execute", null, "escalate", reason,
                null, false, null, "WAITING_APPROVAL", null);
        return support.respond(c, "WAITING_APPROVAL");
    }
}
