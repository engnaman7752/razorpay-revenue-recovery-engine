package com.recovery.api;

import com.recovery.domain.BatchResult;
import com.recovery.domain.BatchResultRepository;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@RestController
public class MetricsController {

    private final BatchResultRepository batchResultRepository;

    public MetricsController(BatchResultRepository batchResultRepository) {
        this.batchResultRepository = batchResultRepository;
    }

    /** Latest batch run: one metrics object per strategy. */
    @GetMapping("/api/metrics")
    public Map<String, Object> metrics() {
        Map<String, Object> body = new LinkedHashMap<>();
        batchResultRepository.findFirstByOrderByIdDesc().ifPresent(latest -> {
            body.put("run_id", latest.getRunId());
            List<BatchResult> rows = batchResultRepository.findByRunIdOrderById(latest.getRunId());
            Map<String, Object> strategies = new LinkedHashMap<>();
            for (BatchResult row : rows) {
                strategies.put(row.getStrategy(), row.getMetrics());
            }
            body.put("strategies", strategies);
        });
        return body;
    }
}
