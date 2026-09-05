package com.recovery.api;

import com.recovery.agent.AgentClient;
import com.recovery.domain.DecisionLog;
import com.recovery.domain.DecisionLogRepository;
import com.recovery.domain.RecoveryCase;
import com.recovery.domain.RecoveryCaseRepository;
import org.springframework.data.domain.Sort;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.springframework.http.HttpStatus.NOT_FOUND;

/**
 * Read API for the dashboard, plus a manual trigger to run a case through
 * the agent (also used by Phase 5/6 verification).
 */
@RestController
public class CaseController {

    private final RecoveryCaseRepository caseRepository;
    private final DecisionLogRepository decisionLogRepository;
    private final AgentClient agentClient;

    public CaseController(RecoveryCaseRepository caseRepository,
            DecisionLogRepository decisionLogRepository,
            AgentClient agentClient) {
        this.caseRepository = caseRepository;
        this.decisionLogRepository = decisionLogRepository;
        this.agentClient = agentClient;
    }

    @GetMapping("/api/cases")
    public List<Map<String, Object>> list() {
        return caseRepository.findAll(Sort.by(Sort.Direction.DESC, "createdAt")).stream()
                .map(this::caseSummary)
                .toList();
    }

    @GetMapping("/api/cases/{id}")
    public Map<String, Object> detail(@PathVariable String id) {
        RecoveryCase c = find(id);
        Map<String, Object> body = caseSummary(c);
        body.put("customer_history", c.getCustomerHistory());
        body.put("timeline", decisionLogRepository.findByCaseIdOrderByTsAsc(c.getId()).stream()
                .map(this::logEntry).toList());
        return body;
    }

    /** Run this case through the agent now (live mode: no auto-approval). */
    @PostMapping("/api/cases/{id}/process")
    public Map<String, Object> process(@PathVariable String id) {
        RecoveryCase c = find(id);
        return agentClient.decide(c, false, "");
    }

    private RecoveryCase find(String id) {
        return caseRepository.findById(UUID.fromString(id))
                .orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "no such case"));
    }

    private Map<String, Object> caseSummary(RecoveryCase c) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("case_id", c.getId().toString());
        m.put("razorpay_order_id", c.getRazorpayOrderId());
        m.put("amount_paise", c.getAmountPaise());
        m.put("currency", c.getCurrency());
        m.put("error_reason", c.getErrorReason());
        m.put("diagnosis", c.getDiagnosis());
        m.put("status", c.getStatus().name());
        m.put("attempts", c.getAttempts());
        m.put("contacts_made", c.getContactsMade());
        m.put("recovered_paise", c.getRecoveredPaise());
        m.put("customer_id", c.getCustomerId());
        m.put("source", c.getSource());
        m.put("created_at", c.getCreatedAt().toString());
        m.put("updated_at", c.getUpdatedAt().toString());
        return m;
    }

    private Map<String, Object> logEntry(DecisionLog e) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("id", e.getId());
        m.put("ts", e.getTs().toString());
        m.put("node", e.getNode());
        m.put("inputs_seen", e.getInputsSeen());
        m.put("action_chosen", e.getActionChosen());
        m.put("reasoning", e.getReasoning());
        m.put("ev_score", e.getEvScore());
        m.put("blocked", e.isBlocked());
        m.put("block_reason", e.getBlockReason());
        m.put("outcome", e.getOutcome());
        m.put("attempt_number", e.getAttemptNumber());
        return m;
    }
}
