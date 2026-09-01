package com.recovery.tools;

import com.recovery.domain.CaseStatus;
import com.recovery.domain.RecoveryCase;
import com.recovery.domain.RecoveryCaseRepository;
import com.recovery.razorpay.GatewayResult;
import com.recovery.razorpay.RecoveryAction;
import com.recovery.razorpay.RazorpayGateway;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

import static org.springframework.http.HttpStatus.NOT_FOUND;

/** Shared plumbing for the six tool services: case lookup, gateway resolution,
 * state transitions, and the uniform response shape the agent expects. */
@Component
public class CaseToolSupport {

    private final RecoveryCaseRepository caseRepository;
    private final RazorpayGateway gateway;
    private final com.recovery.domain.EvStatsService evStatsService;

    public CaseToolSupport(RecoveryCaseRepository caseRepository, RazorpayGateway gateway,
                           com.recovery.domain.EvStatsService evStatsService) {
        this.caseRepository = caseRepository;
        this.gateway = gateway;
        this.evStatsService = evStatsService;
    }

    public RecoveryCase find(String caseId) {
        return caseRepository.findById(UUID.fromString(caseId))
                .orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "no such case: " + caseId));
    }

    /** Run a payment-affecting action through the gateway, apply the outcome,
     * and feed the Beta-Bernoulli learning table. Pending (live, async) results
     * teach nothing yet — the outcome arrives later via webhook. */
    public GatewayResult resolve(RecoveryCase c, RecoveryAction action) {
        GatewayResult result = gateway.execute(c, action);
        if (!result.pending()) {
            evStatsService.recordOutcome(
                    com.recovery.razorpay.CauseMap.diagnose(c.getErrorReason()),
                    action.wire(), result.success());
        }
        if (action.isCustomerContact()) {
            c.setContactsMade(c.getContactsMade() + 1);
        } else {
            c.setAttempts(c.getAttempts() + 1);
        }
        if (result.success()) {
            c.setStatus(CaseStatus.RECOVERED);
            c.setRecoveredPaise(c.getAmountPaise());
        } else if (c.getStatus() == CaseStatus.DETECTED
                || c.getStatus() == CaseStatus.WAITING_APPROVAL) {
            c.setStatus(CaseStatus.IN_PROGRESS);
        }
        caseRepository.save(c);
        return result;
    }

    public Map<String, Object> respond(RecoveryCase c, String outcome) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("outcome", outcome);
        body.put("status", c.getStatus().name());
        body.put("attempts", c.getAttempts());
        body.put("contacts_made", c.getContactsMade());
        body.put("recovered_paise", c.getRecoveredPaise());
        return body;
    }

    public void save(RecoveryCase c) {
        caseRepository.save(c);
    }
}
