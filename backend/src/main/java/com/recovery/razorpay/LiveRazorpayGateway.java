package com.recovery.razorpay;

import com.recovery.domain.RecoveryCase;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

/**
 * Real Razorpay test-mode calls. Live actions are asynchronous: creating a
 * retry order or a payment link does not recover money by itself — the
 * webhook (order.paid / payment_link.paid) later marks the case RECOVERED.
 * So every successful API call here returns a PENDING result.
 *
 * Correlation back to the case:
 *   retry order  -> receipt = case id
 *   payment link -> reference_id = case id
 */
@Component
public class LiveRazorpayGateway implements RazorpayGateway {

    private static final Logger log = LoggerFactory.getLogger(LiveRazorpayGateway.class);

    @Value("${recovery.razorpay.key-id:}")
    private String keyId;

    @Value("${recovery.razorpay.key-secret:}")
    private String keySecret;

    private RestClient client() {
        return RestClient.builder()
                .baseUrl("https://api.razorpay.com/v1")
                .defaultHeaders(h -> h.setBasicAuth(keyId, keySecret))
                .build();
    }

    @Override
    @SuppressWarnings("unchecked")
    public GatewayResult execute(RecoveryCase c, RecoveryAction action) {
        if (keyId.isBlank() || keySecret.isBlank()) {
            return GatewayResult.failed("live gateway: RAZORPAY_KEY_ID/SECRET not configured");
        }
        try {
            return switch (action) {
                case RETRY_NOW, SCHEDULE_RETRY_24H -> {
                    Map<String, Object> order = client().post().uri("/orders")
                            .body(Map.of(
                                    "amount", c.getAmountPaise(),
                                    "currency", c.getCurrency(),
                                    "receipt", c.getId().toString(),
                                    "notes", Map.of("recovery_case", c.getId().toString(),
                                                    "kind", action.wire())))
                            .retrieve().body(Map.class);
                    log.info("retry order {} created for case {}", order.get("id"), c.getId());
                    yield GatewayResult.pending("retry order created: " + order.get("id")
                            + " (awaiting payment webhook)");
                }
                case PAYMENT_LINK, REMINDER_WITH_LINK -> {
                    Map<String, Object> link = client().post().uri("/payment_links")
                            .body(Map.of(
                                    "amount", c.getAmountPaise(),
                                    "currency", c.getCurrency(),
                                    // reference_id must be unique per link; webhook takes the part before ':'
                                    "reference_id", c.getId() + ":" + System.currentTimeMillis(),
                                    "description", "Complete your failed payment",
                                    "notes", Map.of("recovery_case", c.getId().toString())))
                            .retrieve().body(Map.class);
                    String url = (String) link.get("short_url");
                    log.info("payment link {} created for case {}", link.get("id"), c.getId());
                    String prefix = action == RecoveryAction.REMINDER_WITH_LINK
                            ? "reminder sent (simulated) with payment link: "
                            : "payment link created: ";
                    yield GatewayResult.pending(prefix + url + " (awaiting payment webhook)");
                }
            };
        } catch (Exception e) {
            log.error("Razorpay API call failed for case {} action {}", c.getId(), action, e);
            return GatewayResult.failed("razorpay API error: " + e.getMessage());
        }
    }
}
