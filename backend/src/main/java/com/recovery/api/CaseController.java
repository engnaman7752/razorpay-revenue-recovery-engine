package com.recovery.api;

import com.recovery.agent.AgentClient;
import com.recovery.domain.CaseStatus;
import com.recovery.domain.DecisionLog;
import com.recovery.domain.DecisionLogRepository;
import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import com.recovery.domain.RecoveryCaseRepository;
import org.springframework.data.domain.Sort;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
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
    private final DecisionLogger decisionLogger;

    public CaseController(RecoveryCaseRepository caseRepository,
            DecisionLogRepository decisionLogRepository,
            AgentClient agentClient,
            DecisionLogger decisionLogger) {
        this.caseRepository = caseRepository;
        this.decisionLogRepository = decisionLogRepository;
        this.agentClient = agentClient;
        this.decisionLogger = decisionLogger;
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

    /** Simulate a live payment failure from Razorpay (for live presentation demo). */
    @PostMapping("/api/demo/simulate-failure")
    public Map<String, Object> simulateFailure(@RequestBody(required = false) Map<String, Object> req) {
        long amountPaise = 249900L;
        String errorReason = "insufficient_fund";
        String customerId = "judge@razorpay.com";
        String errorSource = "customer";

        if (req != null) {
            if (req.get("amount_paise") != null) {
                amountPaise = ((Number) req.get("amount_paise")).longValue();
            }
            if (req.get("error_reason") != null) {
                errorReason = (String) req.get("error_reason");
            }
            if (req.get("customer_id") != null) {
                customerId = (String) req.get("customer_id");
            }
            if (req.get("error_source") != null) {
                errorSource = (String) req.get("error_source");
            }
        }

        String paymentId = "pay_demo_" + System.currentTimeMillis();
        String orderId = "order_demo_" + System.currentTimeMillis();

        RecoveryCase c = new RecoveryCase();
        c.setId(UUID.randomUUID());
        c.setRazorpayPaymentId(paymentId);
        c.setRazorpayOrderId(orderId);
        c.setAmountPaise(amountPaise);
        c.setCurrency("INR");
        c.setErrorReason(errorReason);
        c.setErrorSource(errorSource);
        c.setCustomerId(customerId);
        c.setSource("LIVE");
        c.setStatus(CaseStatus.DETECTED);
        c = caseRepository.save(c);

        decisionLogger.log(c.getId(), "diagnose",
                Map.of("error_reason", errorReason,
                       "error_source", errorSource,
                       "amount_paise", amountPaise),
                null,
                "demo: live case opened for simulated payment failure " + paymentId,
                null, false, null, "OPENED", 0);

        Map<String, Object> decision = null;
        try {
            decision = agentClient.decide(c, false, "");
            c = caseRepository.findById(c.getId()).orElse(c);
        } catch (Exception e) {
            decision = Map.of("error", e.getMessage() == null ? "agent error" : e.getMessage());
        }

        Map<String, Object> result = new LinkedHashMap<>(caseSummary(c));
        result.put("payment_id", paymentId);
        result.put("order_id", orderId);
        result.put("decision", decision);
        return result;
    }

    /** Simulate customer paying a recovery payment link or retry order. */
    @PostMapping("/api/demo/simulate-payment")
    public Map<String, Object> simulatePayment(@RequestBody Map<String, Object> req) {
        String id = (String) req.get("case_id");
        RecoveryCase c = find(id);
        c.setStatus(CaseStatus.RECOVERED);
        c.setRecoveredPaise(c.getAmountPaise());
        caseRepository.save(c);

        decisionLogger.log(c.getId(), "close",
                Map.of("recovered_paise", c.getRecoveredPaise()),
                null, "demo: customer completed payment via Razorpay recovery link", null, false, null, "RECOVERED", c.getAttempts());

        Map<String, Object> result = new LinkedHashMap<>(caseSummary(c));
        result.put("status", "RECOVERED");
        return result;
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
