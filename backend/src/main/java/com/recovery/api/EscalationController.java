package com.recovery.api;

import com.recovery.agent.AgentClient;
import com.recovery.domain.CaseStatus;
import com.recovery.domain.RecoveryCase;
import com.recovery.domain.RecoveryCaseRepository;
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

import static org.springframework.http.HttpStatus.CONFLICT;
import static org.springframework.http.HttpStatus.NOT_FOUND;

/** Human approval queue: list paused high-value cases; approve/reject resumes
 * the agent's graph from its Postgres checkpoint. */
@RestController
public class EscalationController {

    private final RecoveryCaseRepository caseRepository;
    private final AgentClient agentClient;

    public EscalationController(RecoveryCaseRepository caseRepository, AgentClient agentClient) {
        this.caseRepository = caseRepository;
        this.agentClient = agentClient;
    }

    @GetMapping("/api/escalations")
    public List<Map<String, Object>> pending() {
        return caseRepository.findByStatus(CaseStatus.WAITING_APPROVAL).stream()
                .map(c -> {
                    Map<String, Object> row = new LinkedHashMap<String, Object>();
                    row.put("case_id", c.getId().toString());
                    row.put("amount_paise", c.getAmountPaise());
                    row.put("error_reason", c.getErrorReason());
                    row.put("diagnosis", c.getDiagnosis());
                    row.put("customer_id", c.getCustomerId());
                    row.put("created_at", c.getCreatedAt().toString());
                    return row;
                })
                .toList();
    }

    @PostMapping("/api/escalations/{caseId}/resolve")
    public Map<String, Object> resolve(@PathVariable String caseId,
                                       @RequestBody Map<String, Object> body) {
        boolean approved = Boolean.TRUE.equals(body.get("approved"));
        RecoveryCase c = caseRepository.findById(UUID.fromString(caseId))
                .orElseThrow(() -> new ResponseStatusException(NOT_FOUND, "no such case"));
        if (c.getStatus() != CaseStatus.WAITING_APPROVAL) {
            throw new ResponseStatusException(CONFLICT,
                    "case is not waiting for approval (status " + c.getStatus() + ")");
        }

        if (!approved) {
            c.setStatus(CaseStatus.ESCALATED);   // human took it over; agent stands down
            caseRepository.save(c);
        }
        Map<String, Object> response = agentClient.resume(c, approved);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("case_id", caseId);
        result.put("approved", approved);
        result.put("final_status", response.get("status"));
        result.put("recovered_paise", response.get("recovered_paise"));
        return result;
    }
}
