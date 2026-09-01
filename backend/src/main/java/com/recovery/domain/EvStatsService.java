package com.recovery.domain;

import jakarta.annotation.PostConstruct;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Beta-Bernoulli learning over (cause, action) pairs, stored in ev_stats.
 * Priors mirror agent/graph/ev.py PRIORS — keep the two in sync.
 * Every executed payment/contact action updates alpha (success) or beta
 * (failure); the current counts ride along on each /decide call.
 */
@Service
public class EvStatsService {

    // cause -> action -> {alpha, beta}
    private static final Map<String, Map<String, int[]>> PRIORS = Map.of(
            "SOFT_DECLINE", Map.of(
                    "schedule_retry_24h", new int[]{11, 9},
                    "retry_now", new int[]{3, 17},
                    "payment_link", new int[]{4, 16},
                    "reminder_with_link", new int[]{2, 18}),
            "TRANSIENT", Map.of(
                    "retry_now", new int[]{15, 5},
                    "schedule_retry_24h", new int[]{6, 14},
                    "payment_link", new int[]{2, 18},
                    "reminder_with_link", new int[]{1, 19}),
            "HARD_DECLINE", Map.of(
                    "payment_link", new int[]{8, 12},
                    "reminder_with_link", new int[]{4, 16},
                    "retry_now", new int[]{1, 49},
                    "schedule_retry_24h", new int[]{1, 49}),
            "CUSTOMER_ACTION", Map.of(
                    "reminder_with_link", new int[]{7, 13},
                    "payment_link", new int[]{5, 15},
                    "retry_now", new int[]{2, 18},
                    "schedule_retry_24h", new int[]{2, 18}),
            "UNRECOVERABLE", Map.of(
                    "payment_link", new int[]{2, 18},
                    "reminder_with_link", new int[]{1, 19},
                    "retry_now", new int[]{1, 49},
                    "schedule_retry_24h", new int[]{1, 49}));

    private final EvStatRepository repository;

    public EvStatsService(EvStatRepository repository) {
        this.repository = repository;
    }

    @PostConstruct
    void seedIfEmpty() {
        if (repository.count() == 0) {
            resetToPriors();
        }
    }

    @Transactional
    public void resetToPriors() {
        repository.deleteAllInBatch();
        PRIORS.forEach((cause, actions) -> actions.forEach((action, ab) ->
                repository.save(new EvStat(cause, action, ab[0], ab[1]))));
    }

    @Transactional
    public void recordOutcome(String cause, String action, boolean success) {
        EvStat stat = repository.findByCauseAndAction(cause, action)
                .orElseGet(() -> new EvStat(cause, action, 1, 49));
        if (success) {
            stat.setAlpha(stat.getAlpha() + 1);
        } else {
            stat.setBeta(stat.getBeta() + 1);
        }
        repository.save(stat);
    }

    /** Shape sent to the agent: {cause: {action: [alpha, beta]}} */
    public Map<String, Map<String, List<Integer>>> getStatsWire() {
        Map<String, Map<String, List<Integer>>> wire = new LinkedHashMap<>();
        for (EvStat s : repository.findAll()) {
            wire.computeIfAbsent(s.getCause(), k -> new LinkedHashMap<>())
                    .put(s.getAction(), List.of(s.getAlpha(), s.getBeta()));
        }
        return wire;
    }
}
