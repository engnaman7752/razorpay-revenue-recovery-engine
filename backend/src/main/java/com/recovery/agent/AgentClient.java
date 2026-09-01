package com.recovery.agent;

import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.math.BigDecimal;
import java.time.Duration;
import java.util.List;
import java.util.Map;

/**
 * Backend -> agent bridge. Calls the Python service's /decide (and, from
 * Phase 5, /resume) with a 30s timeout, then persists the agent's decision
 * trace to decision_log. Trace entries with node="execute" are skipped —
 * the tool endpoints already logged those in real time.
 */
@Service
public class AgentClient {

    private final RestClient restClient;
    private final DecisionLogger decisionLogger;
    private final com.recovery.domain.EvStatsService evStatsService;
    private final com.recovery.domain.RecoveryCaseRepository caseRepository;

    public AgentClient(@Value("${recovery.agent-base-url}") String agentBaseUrl,
                       DecisionLogger decisionLogger,
                       com.recovery.domain.EvStatsService evStatsService,
                       com.recovery.domain.RecoveryCaseRepository caseRepository) {
        this.evStatsService = evStatsService;
        this.caseRepository = caseRepository;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(5));
        factory.setReadTimeout(Duration.ofSeconds(30));
        this.restClient = RestClient.builder().baseUrl(agentBaseUrl).requestFactory(factory).build();
        this.decisionLogger = decisionLogger;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> decide(RecoveryCase c, boolean autoApprove, String nowIso) {
        boolean optedOut = c.getCustomerHistory() != null
                && Boolean.TRUE.equals(c.getCustomerHistory().get("opted_out"));

        Map<String, Object> request = Map.of(
                "case_id", c.getId().toString(),
                "amount_paise", c.getAmountPaise(),
                "error_reason", c.getErrorReason() == null ? "" : c.getErrorReason(),
                "opted_out", optedOut,
                "attempts", c.getAttempts(),
                "contacts_made", c.getContactsMade(),
                "auto_approve", autoApprove,
                "now", nowIso == null ? "" : nowIso,
                "ev_stats", evStatsService.getStatsWire());

        Map<String, Object> response = restClient.post().uri("/decide")
                .body(request).retrieve().body(Map.class);

        if (response.get("diagnosis") != null) {
            RecoveryCase latest = caseRepository.findById(c.getId()).orElse(c);
            latest.setDiagnosis((String) response.get("diagnosis"));
            caseRepository.save(latest);
        }
        persistTrace(c, (List<Map<String, Object>>) response.get("trace"));
        return response;
    }

    /** Deliver a human approve/reject decision; the agent continues the paused
     * graph from its Postgres checkpoint. The response's trace holds only the
     * NEW entries produced after the pause. */
    @SuppressWarnings("unchecked")
    public Map<String, Object> resume(RecoveryCase c, boolean approved) {
        Map<String, Object> response = restClient.post().uri("/resume")
                .body(Map.of("case_id", c.getId().toString(), "approved", approved))
                .retrieve().body(Map.class);
        persistTrace(c, (List<Map<String, Object>>) response.get("trace"));
        return response;
    }

    private void persistTrace(RecoveryCase c, List<Map<String, Object>> trace) {
        if (trace == null) {
            return;
        }
        for (Map<String, Object> e : trace) {
            String node = (String) e.get("node");
            if ("execute".equals(node)) {
                continue; // already logged by the tool endpoint itself
            }
            Object ev = e.get("ev_score");
            decisionLogger.log(c.getId(), node,
                    (Map<String, Object>) e.get("inputs_seen"),
                    (String) e.get("action_chosen"),
                    (String) e.get("reasoning"),
                    ev == null ? null : new BigDecimal(ev.toString()),
                    Boolean.TRUE.equals(e.get("blocked")),
                    (String) e.get("block_reason"),
                    (String) e.get("outcome"),
                    e.get("attempt_number") == null ? null
                            : ((Number) e.get("attempt_number")).intValue());
        }
    }
}
