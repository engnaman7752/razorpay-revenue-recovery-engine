package com.recovery.batch;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.recovery.domain.CaseStatus;
import com.recovery.domain.DecisionLogRepository;
import com.recovery.domain.RecoveryCase;
import com.recovery.domain.RecoveryCaseRepository;
import com.recovery.domain.ScheduledRetryRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Loads data/cases.jsonl into recovery_case, wiping previous synthetic state first. */
@Service
public class CaseLoader {

    private final RecoveryCaseRepository caseRepository;
    private final DecisionLogRepository decisionLogRepository;
    private final ScheduledRetryRepository scheduledRetryRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${recovery.cases-file:data/cases.jsonl}")
    private String casesFile;

    public CaseLoader(RecoveryCaseRepository caseRepository,
                      DecisionLogRepository decisionLogRepository,
                      ScheduledRetryRepository scheduledRetryRepository) {
        this.caseRepository = caseRepository;
        this.decisionLogRepository = decisionLogRepository;
        this.scheduledRetryRepository = scheduledRetryRepository;
    }

    @SuppressWarnings("unchecked")
    @Transactional
    public List<RecoveryCase> loadFresh() {
        scheduledRetryRepository.deleteAllInBatch();
        decisionLogRepository.deleteAllInBatch();
        caseRepository.deleteAllInBatch();

        List<RecoveryCase> cases = new ArrayList<>();
        try {
            for (String line : Files.readAllLines(Path.of(casesFile))) {
                if (line.isBlank()) {
                    continue;
                }
                Map<String, Object> row = objectMapper.readValue(line, Map.class);
                RecoveryCase c = new RecoveryCase();
                c.setId(UUID.fromString((String) row.get("id")));
                c.setRazorpayOrderId((String) row.get("razorpay_order_id"));
                c.setRazorpayPaymentId((String) row.get("razorpay_payment_id"));
                c.setAmountPaise(((Number) row.get("amount_paise")).longValue());
                c.setCurrency((String) row.get("currency"));
                c.setErrorReason((String) row.get("error_reason"));
                c.setErrorSource((String) row.get("error_source"));
                c.setCustomerId((String) row.get("customer_id"));
                c.setCustomerHistory((Map<String, Object>) row.get("customer_history"));
                c.setSource((String) row.get("source"));
                c.setGroundTruth((Map<String, Object>) row.get("ground_truth"));
                c.setStatus(CaseStatus.DETECTED);
                cases.add(c);
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to read " + casesFile, e);
        }
        return caseRepository.saveAll(cases);
    }
}
