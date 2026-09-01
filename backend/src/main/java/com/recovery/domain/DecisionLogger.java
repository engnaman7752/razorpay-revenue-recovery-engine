package com.recovery.domain;

import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.util.Map;
import java.util.UUID;

/**
 * Single place every decision/action gets written to the audit trail.
 * Used by the batch strategies now and by the agent tool endpoints later.
 */
@Service
public class DecisionLogger {

    private final DecisionLogRepository repository;

    public DecisionLogger(DecisionLogRepository repository) {
        this.repository = repository;
    }

    public DecisionLog log(UUID caseId, String node, Map<String, Object> inputsSeen,
                           String actionChosen, String reasoning, BigDecimal evScore,
                           boolean blocked, String blockReason, String outcome,
                           Integer attemptNumber) {
        DecisionLog entry = new DecisionLog();
        entry.setCaseId(caseId);
        entry.setNode(node);
        entry.setInputsSeen(inputsSeen);
        entry.setActionChosen(actionChosen);
        entry.setReasoning(reasoning);
        entry.setEvScore(evScore);
        entry.setBlocked(blocked);
        entry.setBlockReason(blockReason);
        entry.setOutcome(outcome);
        entry.setAttemptNumber(attemptNumber);
        return repository.save(entry);
    }

    /** Convenience for a simple executed action. */
    public DecisionLog logAction(UUID caseId, String action, String reasoning,
                                 String outcome, Integer attemptNumber) {
        return log(caseId, "execute", null, action, reasoning, null,
                false, null, outcome, attemptNumber);
    }
}
