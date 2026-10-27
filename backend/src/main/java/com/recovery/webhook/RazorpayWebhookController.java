package com.recovery.webhook;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.recovery.agent.AgentClient;
import com.recovery.api.SseController;
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
    private final SseController sseController;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final ExecutorService agentExecutor = Executors.newSingleThreadExecutor();

    @Value("${recovery.razorpay.webhook-secret:}")
    private String webhookSecret;

    public RazorpayWebhookController(RecoveryCaseRepository caseRepository,
                                     AgentClient agentClient, DecisionLogger decisionLogger,
                                     SseController sseController) {
        this.caseRepository = caseRepository;
        this.agentClient = agentClient;
        this.decisionLogger = decisionLogger;
        this.sseController = sseController;
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
            case "payment.failed" -> paymentFailed(payload);
            case "payment_link.paid" -> linkPaid(entity(payload, "payment_link"));
            case "order.paid" -> orderPaid(entity(payload, "order"));
            case "payment.captured", "payment.authorized" -> paymentCaptured(entity(payload, "payment"));
            default -> ResponseEntity.ok(Map.of("ignored", eventType == null ? "?" : eventType));
        };
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> entity(Map<String, Object> payload, String key) {
        Map<String, Object> wrapper = (Map<String, Object>) payload.getOrDefault(key, Map.of());
        return (Map<String, Object>) wrapper.getOrDefault("entity", Map.of());
    }

    @SuppressWarnings("unchecked")
    private ResponseEntity<Map<String, Object>> paymentFailed(Map<String, Object> payload) {
        Map<String, Object> payment = entity(payload, "payment");
        Map<String, Object> paymentLink = entity(payload, "payment_link");
        Map<String, Object> order = entity(payload, "order");

        String paymentId = (String) payment.get("id");
        if (paymentId != null && caseRepository.findByRazorpayPaymentId(paymentId).isPresent()) {
            return ResponseEntity.ok(Map.of("duplicate", paymentId));
        }

        // --- 1. Check if payload has payment_link entity with reference_id / notes ---
        if (paymentLink != null && !paymentLink.isEmpty()) {
            String ref = (String) paymentLink.get("reference_id");
            UUID caseId = parseCaseId(ref);
            if (caseId != null) {
                var existing = caseRepository.findById(caseId);
                if (existing.isPresent()) {
                    return retryFailedOnExistingCase(existing.get(), payment, "payment link reference " + ref);
                }
            }
            if (paymentLink.get("notes") instanceof Map<?, ?> linkNotes) {
                String noteCaseId = (String) linkNotes.get("recovery_case");
                UUID cid = parseCaseId(noteCaseId);
                if (cid != null) {
                    var existing = caseRepository.findById(cid);
                    if (existing.isPresent()) {
                        return retryFailedOnExistingCase(existing.get(), payment, "payment link note");
                    }
                }
            }
        }

        // --- 2. Check if payload has order entity with receipt / notes ---
        if (order != null && !order.isEmpty()) {
            String receipt = (String) order.get("receipt");
            UUID caseId = parseCaseId(receipt);
            if (caseId != null) {
                var existing = caseRepository.findById(caseId);
                if (existing.isPresent()) {
                    return retryFailedOnExistingCase(existing.get(), payment, "order receipt " + receipt);
                }
            }
            if (order.get("notes") instanceof Map<?, ?> orderNotes) {
                String noteCaseId = (String) orderNotes.get("recovery_case");
                UUID cid = parseCaseId(noteCaseId);
                if (cid != null) {
                    var existing = caseRepository.findById(cid);
                    if (existing.isPresent()) {
                        return retryFailedOnExistingCase(existing.get(), payment, "order note");
                    }
                }
            }
        }

        // --- 3. Check if payment has order_id registered on an existing case ---
        String orderId = (String) payment.get("order_id");
        if (orderId != null && !orderId.isBlank()) {
            List<RecoveryCase> orderMatches = caseRepository.findAllByRazorpayOrderId(orderId);
            if (!orderMatches.isEmpty()) {
                // Find active (non-closed, non-recovered) case first, or the newest case
                RecoveryCase target = orderMatches.stream()
                        .filter(ec -> ec.getStatus() != CaseStatus.RECOVERED && ec.getStatus() != CaseStatus.CLOSED)
                        .sorted((a, b) -> b.getCreatedAt().compareTo(a.getCreatedAt()))
                        .findFirst()
                        .orElse(orderMatches.get(0));
                return retryFailedOnExistingCase(target, payment, "retry order " + orderId);
            }
        }

        // --- 4. Check if payment entity has notes.recovery_case ---
        if (payment.get("notes") instanceof Map<?, ?> notesMap) {
            String caseIdStr = (String) notesMap.get("recovery_case");
            UUID caseId = parseCaseId(caseIdStr);
            if (caseId != null) {
                var existing = caseRepository.findById(caseId);
                if (existing.isPresent()) {
                    return retryFailedOnExistingCase(existing.get(), payment, "payment notes");
                }
            }
        }

        // --- 5. Fallback matching: Same customer + same amount with an active open case ---
        long amountPaise = ((Number) payment.getOrDefault("amount", 0)).longValue();
        String customerId = (String) payment.get("email");
        if (customerId == null || customerId.isBlank()) {
            customerId = (String) payment.get("contact");
        }
        if (customerId != null && !customerId.isBlank() && amountPaise > 0) {
            final String finalCust = customerId.trim();
            var activeMatches = caseRepository.findAll().stream()
                    .filter(ec -> "LIVE".equals(ec.getSource()))
                    .filter(ec -> ec.getCustomerId() != null && finalCust.equalsIgnoreCase(ec.getCustomerId().trim()))
                    .filter(ec -> ec.getAmountPaise() == amountPaise)
                    .filter(ec -> ec.getStatus() != CaseStatus.RECOVERED && ec.getStatus() != CaseStatus.CLOSED)
                    .sorted((a, b) -> b.getCreatedAt().compareTo(a.getCreatedAt()))
                    .toList();
            if (!activeMatches.isEmpty()) {
                return retryFailedOnExistingCase(activeMatches.get(0), payment, "active recovery for " + customerId);
            }
        }

        // --- Genuinely new failed payment: open a fresh case ---
        RecoveryCase c = new RecoveryCase();
        c.setId(UUID.randomUUID());
        c.setRazorpayPaymentId(paymentId);
        c.setRazorpayOrderId(orderId);
        c.setAmountPaise(amountPaise);
        c.setCurrency((String) payment.getOrDefault("currency", "INR"));
        c.setErrorReason((String) payment.get("error_reason"));
        c.setErrorSource((String) payment.get("error_source"));
        c.setCustomerId(customerId);
        c.setSource("LIVE");
        c.setStatus(CaseStatus.DETECTED);
        caseRepository.save(c);

        sseController.broadcast("case_update", Map.of("case_id", c.getId().toString(), "status", "DETECTED", "amount_paise", c.getAmountPaise(), "error_reason", c.getErrorReason() != null ? c.getErrorReason() : "", "source", "LIVE"));

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

    /** A payment failed on a recovery link or retry order that belongs to an
     *  existing case. Log it on the ORIGINAL case's timeline and re-run the
     *  agent so it can decide the next action (escalate, try a different
     *  channel, or close as unrecoverable). */
    private ResponseEntity<Map<String, Object>> retryFailedOnExistingCase(
            RecoveryCase c, Map<String, Object> payment, String via) {

        String paymentId = (String) payment.get("id");
        String newReason = (String) payment.get("error_reason");
        c.setAttempts(c.getAttempts() + 1);
        c.setErrorReason(newReason != null ? newReason : c.getErrorReason());
        c.setStatus(CaseStatus.DETECTED);  // reset so agent re-evaluates
        caseRepository.save(c);

        sseController.broadcast("case_update", Map.of("case_id", c.getId().toString(), "status", "RETRY_FAILED", "attempt", c.getAttempts(), "error_reason", newReason != null ? newReason : ""));

        decisionLogger.log(c.getId(), "check_outcome",
                Map.of("event", "payment.failed",
                       "payment_id", paymentId != null ? paymentId : "",
                       "via", via,
                       "new_error", newReason != null ? newReason : ""),
                null,
                "recovery attempt failed via " + via + ": " + paymentId
                        + " (" + newReason + ") — re-evaluating",
                null, false, null, "RETRY_FAILED", c.getAttempts());
        log.info("case {} recovery attempt failed via {} (payment {}), re-evaluating",
                c.getId(), via, paymentId);

        agentExecutor.submit(() -> {
            try {
                agentClient.decide(c, false, "");
            } catch (Exception e) {
                log.error("agent re-evaluation failed on case {}", c.getId(), e);
            }
        });
        return ResponseEntity.ok(Map.of("case_id", c.getId().toString(),
                "linked_to_existing", true, "attempt", c.getAttempts()));
    }

    private ResponseEntity<Map<String, Object>> linkPaid(Map<String, Object> link) {
        // LiveRazorpayGateway packs the case id into reference_id
        String ref = (String) link.get("reference_id");
        return recover(ref, "payment link " + link.get("id") + " paid");
    }

    private ResponseEntity<Map<String, Object>> orderPaid(Map<String, Object> order) {
        String receipt = (String) order.get("receipt");
        UUID id = parseCaseId(receipt);
        if (id != null && caseRepository.findById(id).isPresent()) {
            return recover(receipt, "retry order " + order.get("id") + " paid");
        }
        String orderId = (String) order.get("id");
        if (orderId != null && !orderId.isBlank()) {
            List<RecoveryCase> matches = caseRepository.findAllByRazorpayOrderId(orderId);
            if (!matches.isEmpty()) {
                return recover(matches.get(0).getId().toString(), "order " + orderId + " paid");
            }
        }
        return recover(receipt, "retry order " + order.get("id") + " paid");
    }

    private ResponseEntity<Map<String, Object>> paymentCaptured(Map<String, Object> payment) {
        String paymentId = (String) payment.get("id");
        String orderId = (String) payment.get("order_id");
        long amountPaise = ((Number) payment.getOrDefault("amount", 0)).longValue();
        String customerId = (String) payment.get("email");
        if (customerId == null || customerId.isBlank()) {
            customerId = (String) payment.get("contact");
        }

        // 1. Check notes on payment
        if (payment.get("notes") instanceof Map<?, ?> notesMap) {
            String caseIdStr = (String) notesMap.get("recovery_case");
            UUID cid = parseCaseId(caseIdStr);
            if (cid != null) {
                return recover(cid.toString(), "payment " + paymentId + " captured (via notes)");
            }
        }

        // 2. Check if orderId matches any case
        if (orderId != null && !orderId.isBlank()) {
            List<RecoveryCase> matches = caseRepository.findAllByRazorpayOrderId(orderId);
            if (!matches.isEmpty()) {
                RecoveryCase target = matches.stream()
                        .filter(ec -> ec.getStatus() != CaseStatus.RECOVERED && ec.getStatus() != CaseStatus.CLOSED)
                        .sorted((a, b) -> b.getCreatedAt().compareTo(a.getCreatedAt()))
                        .findFirst()
                        .orElse(matches.get(0));
                return recover(target.getId().toString(), "payment " + paymentId + " captured for order " + orderId);
            }
        }

        // 3. Fallback match by active case for same customer and amount
        if (customerId != null && !customerId.isBlank() && amountPaise > 0) {
            final String finalCust = customerId.trim();
            var activeMatches = caseRepository.findAll().stream()
                    .filter(ec -> "LIVE".equals(ec.getSource()))
                    .filter(ec -> ec.getCustomerId() != null && finalCust.equalsIgnoreCase(ec.getCustomerId().trim()))
                    .filter(ec -> ec.getAmountPaise() == amountPaise)
                    .filter(ec -> ec.getStatus() != CaseStatus.RECOVERED && ec.getStatus() != CaseStatus.CLOSED)
                    .sorted((a, b) -> b.getCreatedAt().compareTo(a.getCreatedAt()))
                    .toList();
            if (!activeMatches.isEmpty()) {
                return recover(activeMatches.get(0).getId().toString(), "payment " + paymentId + " captured for " + customerId);
            }
        }

        return ResponseEntity.ok(Map.of("ignored", "unmatched payment " + paymentId));
    }

    /** Recover the case UUID from a payment-link reference_id. Supports the
     *  packed form "<32-hex><suffix>" and the legacy "<uuid>:<ts>" form. */
    static String caseIdFromReference(String ref) {
        if (ref == null) return null;
        if (ref.contains(":")) return ref.split(":")[0];            // legacy
        if (ref.length() >= 32) {
            String h = ref.substring(0, 32);
            if (h.matches("[0-9a-fA-F]{32}")) {
                return h.replaceFirst("(.{8})(.{4})(.{4})(.{4})(.{12})",
                                      "$1-$2-$3-$4-$5");
            }
        }
        return ref;
    }

    /** Parse a case UUID from a webhook value, tolerating anything that isn't
     *  ours. Paying a payment LINK makes Razorpay also fire order.paid for the
     *  link's internal order, whose receipt is Razorpay's own value, not our
     *  case id — that must be ignored, never crash the webhook. */
    static UUID parseCaseId(String raw) {
        if (raw == null) return null;
        try {
            return UUID.fromString(caseIdFromReference(raw));
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    private ResponseEntity<Map<String, Object>> recover(String rawId, String how) {
        UUID id = parseCaseId(rawId);
        if (id == null) {
            return ResponseEntity.ok(Map.of("ignored", "not a recovery case: " + rawId));
        }
        return caseRepository.findById(id).map(c -> {
            if (c.getStatus() != CaseStatus.RECOVERED) {
                c.setStatus(CaseStatus.RECOVERED);
                c.setRecoveredPaise(c.getAmountPaise());
                caseRepository.save(c);
                sseController.broadcast("case_update", Map.of("case_id", c.getId().toString(), "status", "RECOVERED", "recovered_paise", c.getAmountPaise()));
                decisionLogger.log(c.getId(), "check_outcome", null, null,
                        "webhook: " + how, null, false, null, "RECOVERED", null);
                log.info("case {} RECOVERED via webhook ({})", id, how);
            }
            return ResponseEntity.ok(Map.<String, Object>of("case_id", id.toString(), "status", "RECOVERED"));
        }).orElse(ResponseEntity.ok(Map.of("ignored", "unknown case " + id)));
    }
}
