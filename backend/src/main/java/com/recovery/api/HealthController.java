package com.recovery.api;

import com.recovery.domain.RecoveryCaseRepository;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class HealthController {

    private final RecoveryCaseRepository caseRepository;

    public HealthController(RecoveryCaseRepository caseRepository) {
        this.caseRepository = caseRepository;
    }

    /** Proves the service is up AND the database is reachable (count() hits Postgres). */
    @GetMapping("/api/health")
    public Map<String, Object> health() {
        return Map.of(
                "status", "ok",
                "cases_in_db", caseRepository.count()
        );
    }
}
