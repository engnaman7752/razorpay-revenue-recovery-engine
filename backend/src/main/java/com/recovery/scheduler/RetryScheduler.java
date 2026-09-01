package com.recovery.scheduler;

import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import com.recovery.domain.RecoveryCaseRepository;
import com.recovery.domain.ScheduledRetry;
import com.recovery.domain.ScheduledRetryRepository;
import com.recovery.razorpay.GatewayResult;
import com.recovery.razorpay.RecoveryAction;
import com.recovery.tools.CaseToolSupport;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.OffsetDateTime;
import java.util.List;

/** Every 60s, executes scheduled retries that have come due (live mode parks
 * them via the schedule-retry tool; simulated mode resolves instantly). */
@Component
public class RetryScheduler {

    private static final Logger log = LoggerFactory.getLogger(RetryScheduler.class);

    private final ScheduledRetryRepository scheduledRetryRepository;
    private final RecoveryCaseRepository caseRepository;
    private final CaseToolSupport support;
    private final DecisionLogger decisionLogger;

    public RetryScheduler(ScheduledRetryRepository scheduledRetryRepository,
                          RecoveryCaseRepository caseRepository,
                          CaseToolSupport support, DecisionLogger decisionLogger) {
        this.scheduledRetryRepository = scheduledRetryRepository;
        this.caseRepository = caseRepository;
        this.support = support;
        this.decisionLogger = decisionLogger;
    }

    @Scheduled(fixedDelay = 60_000)
    public void runDueRetries() {
        List<ScheduledRetry> due =
                scheduledRetryRepository.findByExecutedFalseAndDueAtBefore(OffsetDateTime.now());
        for (ScheduledRetry retry : due) {
            retry.setExecuted(true);
            scheduledRetryRepository.save(retry);
            caseRepository.findById(retry.getCaseId()).ifPresent(this::execute);
        }
    }

    private void execute(RecoveryCase c) {
        GatewayResult result = support.resolve(c, RecoveryAction.SCHEDULE_RETRY_24H);
        String outcome = result.success() ? "RECOVERED" : result.pending() ? "PENDING" : "FAILED";
        decisionLogger.logAction(c.getId(), RecoveryAction.SCHEDULE_RETRY_24H.wire(),
                "scheduled retry executed: " + result.detail(), outcome, c.getAttempts());
        log.info("scheduled retry for case {} -> {}", c.getId(), outcome);
    }
}
