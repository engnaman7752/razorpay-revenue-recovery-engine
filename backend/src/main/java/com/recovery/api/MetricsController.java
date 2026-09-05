package com.recovery.api;

import com.recovery.domain.BatchResult;
import com.recovery.domain.BatchResultRepository;
import com.recovery.domain.CaseStatus;
import com.recovery.domain.RecoveryCase;
import com.recovery.domain.RecoveryCaseRepository;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class MetricsController {

    private final BatchResultRepository batchResultRepository;
    private final RecoveryCaseRepository caseRepository;

    public MetricsController(BatchResultRepository batchResultRepository,
            RecoveryCaseRepository caseRepository) {
        this.batchResultRepository = batchResultRepository;
        this.caseRepository = caseRepository;
    }

    /** Latest batch run + live case overlay. */
    @GetMapping("/api/metrics")
    @SuppressWarnings("unchecked")
    public Map<String, Object> metrics() {
        Map<String, Object> body = new LinkedHashMap<>();
        batchResultRepository.findFirstByOrderByIdDesc().ifPresent(latest -> {
            body.put("run_id", latest.getRunId());
            List<BatchResult> rows = batchResultRepository.findByRunIdOrderById(latest.getRunId());
            Map<String, Object> strategies = new LinkedHashMap<>();
            for (BatchResult row : rows) {
                strategies.put(row.getStrategy(), new LinkedHashMap<>(row.getMetrics()));
            }

            // Merge live case stats into AGENT metrics so Dashboard updates in real time
            Map<String, Object> agentMetrics = (Map<String, Object>) strategies.get("AGENT");
            if (agentMetrics != null) {
                List<RecoveryCase> liveCases = caseRepository.findBySource("LIVE");
                if (!liveCases.isEmpty()) {
                    long liveRecovered = liveCases.stream()
                            .filter(c -> c.getStatus() == CaseStatus.RECOVERED)
                            .mapToLong(RecoveryCase::getRecoveredPaise)
                            .sum();
                    long liveAtRisk = liveCases.stream()
                            .mapToLong(RecoveryCase::getAmountPaise)
                            .sum();
                    long liveRecoveredCount = liveCases.stream()
                            .filter(c -> c.getStatus() == CaseStatus.RECOVERED)
                            .count();

                    // Add live numbers on top of batch numbers
                    agentMetrics.put("recovered_paise",
                            ((Number) agentMetrics.getOrDefault("recovered_paise", 0)).longValue() + liveRecovered);
                    agentMetrics.put("total_at_risk_paise",
                            ((Number) agentMetrics.getOrDefault("total_at_risk_paise", 0)).longValue() + liveAtRisk);
                    agentMetrics.put("cases_recovered",
                            ((Number) agentMetrics.getOrDefault("cases_recovered", 0)).longValue()
                                    + liveRecoveredCount);
                    agentMetrics.put("live_cases", liveCases.size());
                    agentMetrics.put("live_recovered_paise", liveRecovered);
                }
            }

            body.put("strategies", strategies);
        });
        return body;
    }
}
