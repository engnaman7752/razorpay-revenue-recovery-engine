package com.recovery.webhook;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.recovery.agent.AgentClient;
import com.recovery.domain.CaseStatus;
import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import com.recovery.domain.RecoveryCaseRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Receives Razorpay webhooks. Signature is verified against the RAW body
 * bytes before any parsing; mismatch -> 401 and nothing else happens.
 *
 * payment.failed        -> open a LIVE recovery case, hand it to the agent
 * payment_link.paid     -> mark the linked case RECOVERED
 * order.paid            -> mark the case whose retry order was paid RECOVERED
 */
@RestController
public class RazorpayWebhookController {

    private static final Logger log = LoggerFactory.getLogger(RazorpayWebhookController.class);

    private final RecoveryCaseRepository caseRepository;
    private final AgentClient agentClient;
    private final DecisionLogger decisionLogger;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final ExecutorService agentExecutor = Executors.newSingleThreadExecutor();

    @Value("${recovery.razorpay.webhook-secret:}")
    private String webhookSecret;

    public RazorpayWebhookController(RecoveryCaseRepository caseRepository,
                                     AgentClient agentClient, DecisionLogger decisionLogger) {
        this.caseRepository = caseRepository;
        this.agentClient = agentClient;
        this.decisionLogger = decisionLogger;
    }

    @SuppressWarnings("unchecked")
    @PostMapping("/webhook/razorpay")
    public ResponseEntity<Map<String, Object>> handle(
            @RequestBody byte[] rawBody,
            @RequestHeader(value = "X-Razorpay-Signature", required = false) String signature)
            throws Exception {

        if (!SignatureVerifier.verify(rawBody, signature, webhookSecret)) {
            log.warn("webhook rejected: bad or missing signature");
            return ResponseEntity.status(401).body(Map.of("error", "invalid signature"));
        }

        Map<String, Object> event = objectMapper.readValue(rawBody, Map.class);
        String eventType = (String) event.get("event");
        Map<String, Object> payload = (Map<String, Object>) event.getOrDefault("payload", Map.of());

        return switch (eventType == null ? "" : eventType) {
            case "payment.failed" -> paymentFailed(entity(payload, "payment"));
            case "payment_link.paid" -> linkPaid(entity(payload, "payment_link"));
            case "order.paid" -> orderPaid(entity(payload, "order"));
            default -> ResponseEntity.ok(Map.of("ignored", eventType == null ? "?" : eventType));
        };
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> entity(Map<String, Object> payload, String key) {
        Map<String, Object> wrapper = (Map<String, Object>) payload.getOrDefault(key, Map.of());
        return (Map<String, Object>) wrapper.getOrDefault("entity", Map.of());
    }

    private ResponseEntity<Map<String, Object>> paymentFailed(Map<String, Object> payment) {
        String paymentId = (String) payment.get("id");
        if (paymentId != null && caseRepository.findByRazorpayPaymentId(paymentId).isPresent()) {
            return ResponseEntity.ok(Map.of("duplicate", paymentId));
        }

        RecoveryCase c = new RecoveryCase();
        c.setId(UUID.randomUUID());
        c.setRazorpayPaymentId(paymentId);
        c.setRazorpayOrderId((String) payment.get("order_id"));
        c.setAmountPaise(((Number) payment.getOrDefault("amount", 0)).longValue());
        c.setCurrency((String) payment.getOrDefault("currency", "INR"));
        c.setErrorReason((String) payment.get("error_reason"));
        c.setErrorSource((String) payment.get("error_source"));
        c.setCustomerId((String) payment.getOrDefault("email", payment.get("contact")));
        c.setSource("LIVE");
        c.setStatus(CaseStatus.DETECTED);
        caseRepository.save(c);

        decisionLogger.log(c.getId(), "detect", Map.of("event", "payment.failed"),
                null, "webhook: payment " + paymentId + " failed (" + c.getErrorReason() + ")",
                null, false, null, "DETECTED", null);
        log.info("LIVE case {} opened for failed payment {}", c.getId(), paymentId);

        // respond to Razorpay fast; the agent runs in the background
        agentExecutor.submit(() -> {
            try {
                agentClient.decide(c, false, "");
            } catch (Exception e) {
                log.error("agent failed on case {}", c.getId(), e);
            }
        });
        return ResponseEntity.ok(Map.of("case_id", c.getId().toString()));
    }

    private ResponseEntity<Map<String, Object>> linkPaid(Map<String, Object> link) {
        // LiveRazorpayGateway sets reference_id = "<case id>:<timestamp>"
        String ref = (String) link.get("reference_id");
        String caseId = ref == null ? null : ref.split(":")[0];
        return recover(caseId, "payment link " + link.get("id") + " paid");
    }

    private ResponseEntity<Map<String, Object>> orderPaid(Map<String, Object> order) {
        // LiveRazorpayGateway sets receipt = case id when creating a retry order
        return recover((String) order.get("receipt"),
                "retry order " + order.get("id") + " paid");
    }

    private ResponseEntity<Map<String, Object>> recover(String caseId, String how) {
        if (caseId == null) {
            return ResponseEntity.ok(Map.of("ignored", "no case reference"));
        }
        return caseRepository.findById(UUID.fromString(caseId)).map(c -> {
            if (c.getStatus() != CaseStatus.RECOVERED) {
                c.setStatus(CaseStatus.RECOVERED);
                c.setRecoveredPaise(c.getAmountPaise());
                caseRepository.save(c);
                decisionLogger.log(c.getId(), "check_outcome", null, null,
                        "webhook: " + how, null, false, null, "RECOVERED", null);
                log.info("case {} RECOVERED via webhook ({})", caseId, how);
            }
            return ResponseEntity.ok(Map.<String, Object>of("case_id", caseId, "status", "RECOVERED"));
        }).orElse(ResponseEntity.ok(Map.of("ignored", "unknown case " + caseId)));
    }
}
