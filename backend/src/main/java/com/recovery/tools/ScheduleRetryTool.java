package com.recovery.tools;

import com.recovery.domain.CaseStatus;
import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import com.recovery.domain.ScheduledRetry;
import com.recovery.domain.ScheduledRetryRepository;
import com.recovery.razorpay.GatewayResult;
import com.recovery.razorpay.RecoveryAction;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.OffsetDateTime;
import java.util.Map;

/** Delayed retry. Simulated mode collapses time and resolves now; live mode
 * parks a scheduled_retry row that RetryScheduler picks up when due. */
@Service
public class ScheduleRetryTool {

    private final CaseToolSupport support;
    private final DecisionLogger decisionLogger;
    private final ScheduledRetryRepository scheduledRetryRepository;

    @Value("${recovery.gateway-mode:simulated}")
    private String gatewayMode;

    public ScheduleRetryTool(CaseToolSupport support, DecisionLogger decisionLogger,
                             ScheduledRetryRepository scheduledRetryRepository) {
        this.support = support;
        this.decisionLogger = decisionLogger;
        this.scheduledRetryRepository = scheduledRetryRepository;
    }

    public Map<String, Object> run(String caseId, int delayHours) {
        RecoveryCase c = support.find(caseId);

        if ("simulated".equals(gatewayMode)) {
            GatewayResult result = support.resolve(c, RecoveryAction.SCHEDULE_RETRY_24H);
            String outcome = result.success() ? "RECOVERED" : "FAILED";
            decisionLogger.logAction(c.getId(), RecoveryAction.SCHEDULE_RETRY_24H.wire(),
                    result.detail() + " (time collapsed in simulation)", outcome, c.getAttempts());
            return support.respond(c, outcome);
        }

        ScheduledRetry retry = new ScheduledRetry();
        retry.setCaseId(c.getId());
        retry.setDueAt(OffsetDateTime.now().plusHours(delayHours));
        scheduledRetryRepository.save(retry);
        c.setStatus(CaseStatus.SCHEDULED);
        support.save(c);
        decisionLogger.logAction(c.getId(), RecoveryAction.SCHEDULE_RETRY_24H.wire(),
                "retry scheduled in " + delayHours + "h", "SCHEDULED", c.getAttempts());
        return support.respond(c, "SCHEDULED");
    }
}
