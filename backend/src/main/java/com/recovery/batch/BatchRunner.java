package com.recovery.batch;

import com.recovery.domain.BatchResult;
import com.recovery.domain.BatchResultRepository;
import com.recovery.domain.CaseStatus;
import com.recovery.domain.DecisionLogger;
import com.recovery.domain.RecoveryCase;
import com.recovery.domain.RecoveryCaseRepository;
import com.recovery.razorpay.GatewayResult;
import com.recovery.razorpay.RecoveryAction;
import com.recovery.razorpay.SimulatedGateway;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Runs the 300-case synthetic batch through each strategy against the
 * SimulatedGateway and writes eval/results.md plus batch_result rows.
 *
 * Enabled with: java -jar app.jar --recovery.batch.enabled=true
 *
 * Strategies:
 *   DO_NOTHING - baseline floor: never act.
 *   NAIVE      - retry_now up to 3 times on every case, no thinking.
 *   AGENT      - the LangGraph agent (wired in Phase 3; skipped until then).
 *   ORACLE     - reads ground_truth and plays the one correct action; the
 *                ceiling. It still respects customer opt-out (a "perfect"
 *                player is still policy-compliant).
 */
@Component
@ConditionalOnProperty(name = "recovery.batch.enabled", havingValue = "true")
public class BatchRunner implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(BatchRunner.class);
    private static final int NAIVE_MAX_RETRIES = 3;

    private final CaseLoader caseLoader;
    private final SimulatedGateway gateway;   // batch always simulates, whatever GATEWAY_MODE says
    private final RecoveryCaseRepository caseRepository;
    private final DecisionLogger decisionLogger;
    private final BatchResultRepository batchResultRepository;
    private final com.recovery.agent.AgentClient agentClient;
    private final com.recovery.domain.EvStatsService evStatsService;

    @Value("${recovery.results-file:eval/results.md}")
    private String resultsFile;

    @Value("${recovery.batch.include-agent:false}")
    private boolean includeAgent;

    /** Fixed daytime clock handed to the agent so quiet-hours checks are deterministic in batch. */
    @Value("${recovery.batch.now:2026-08-27T12:00:00+05:30}")
    private String batchNow;

    public BatchRunner(CaseLoader caseLoader, SimulatedGateway gateway,
                       RecoveryCaseRepository caseRepository, DecisionLogger decisionLogger,
                       BatchResultRepository batchResultRepository,
                       com.recovery.agent.AgentClient agentClient,
                       com.recovery.domain.EvStatsService evStatsService) {
        this.caseLoader = caseLoader;
        this.gateway = gateway;
        this.caseRepository = caseRepository;
        this.decisionLogger = decisionLogger;
        this.batchResultRepository = batchResultRepository;
        this.agentClient = agentClient;
        this.evStatsService = evStatsService;
    }

    @Override
    public void run(String... args) {
        String runId = java.time.Instant.now().toString();
        log.info("Batch run {} starting", runId);

        Map<String, StrategyResult> results = new LinkedHashMap<>();

        // Execution order: AGENT runs LAST so its cases and decision_log rows are
        // what remains in the database for the dashboard. Presentation order in
        // results.md stays DO_NOTHING, NAIVE, AGENT, ORACLE.
        StrategyResult doNothing = runDoNothing();
        StrategyResult naive = runNaive();
        StrategyResult oracle = runOracle();
        StrategyResult agent = null;
        if (includeAgent) {
            agent = runAgent();
        } else {
            log.info("AGENT strategy skipped (recovery.batch.include-agent=false)");
        }

        results.put("DO_NOTHING", doNothing);
        results.put("NAIVE", naive);
        if (agent != null) {
            results.put("AGENT", agent);
        }
        results.put("ORACLE", oracle);

        long totalAtRisk = caseRepository.findAll().stream().mapToLong(RecoveryCase::getAmountPaise).sum();

        for (StrategyResult r : results.values()) {
            BatchResult row = new BatchResult();
            row.setRunId(runId);
            row.setStrategy(r.strategy);
            row.setMetrics(r.toMetricsMap(oracle.recoveredPaise, totalAtRisk));
            batchResultRepository.save(row);
            // Machine-readable line parsed by ci/verify.sh:
            log.info("RESULT strategy={} recovered_paise={} cases_recovered={} contacts={}",
                    r.strategy, r.recoveredPaise, r.casesRecovered, r.contactsMade);
        }

        writeResultsMarkdown(results, oracle.recoveredPaise, totalAtRisk, runId);
        log.info("Batch run {} complete; wrote {}", runId, resultsFile);
    }

    // ------------------------------------------------------------------
    private StrategyResult runDoNothing() {
        caseLoader.loadFresh();
        StrategyResult r = new StrategyResult("DO_NOTHING");
        for (RecoveryCase c : caseRepository.findAll()) {
            c.setStatus(CaseStatus.CLOSED);
            caseRepository.save(c);
        }
        return r;
    }

    // ------------------------------------------------------------------
    private StrategyResult runNaive() {
        List<RecoveryCase> cases = caseLoader.loadFresh();
        StrategyResult r = new StrategyResult("NAIVE");
        for (RecoveryCase c : cases) {
            for (int attempt = 1; attempt <= NAIVE_MAX_RETRIES; attempt++) {
                GatewayResult result = gateway.execute(c, RecoveryAction.RETRY_NOW);
                r.paymentAttempts++;
                r.actionsTaken++;
                c.setAttempts(attempt);
                decisionLogger.logAction(c.getId(), RecoveryAction.RETRY_NOW.wire(),
                        "naive: always retry", result.success() ? "RECOVERED" : "FAILED", attempt);
                if (result.success()) {
                    recover(c, r);
                    break;
                }
            }
            if (c.getStatus() != CaseStatus.RECOVERED) {
                close(c, "naive: gave up after " + NAIVE_MAX_RETRIES + " retries");
            }
        }
        return r;
    }

    // ------------------------------------------------------------------
    @SuppressWarnings("unchecked")
    private StrategyResult runAgent() {
        List<RecoveryCase> cases = caseLoader.loadFresh();
        evStatsService.resetToPriors();   // learn from this batch alone, not from baseline noise
        StrategyResult r = new StrategyResult("AGENT");

        // learning curve: thirds of the batch in processing order
        int[] thirdCases = new int[3];
        int[] thirdRecovered = new int[3];
        long[] thirdPaise = new long[3];
        int[] thirdContacts = new int[3];
        // per-cause breakdown
        Map<String, long[]> causeAgg = new java.util.LinkedHashMap<>(); // {cases, recovered, paise, contacts}

        int index = 0;
        for (RecoveryCase c : cases) {
            Map<String, Object> response = agentClient.decide(c, true, batchNow);

            if (Boolean.TRUE.equals(response.get("escalated"))) {
                r.escalations++;
            }
            List<Map<String, Object>> trace = (List<Map<String, Object>>) response.get("trace");
            if (trace != null) {
                for (Map<String, Object> e : trace) {
                    if (Boolean.TRUE.equals(e.get("blocked"))) {
                        r.stoppingRuleActivations++;
                    }
                    String reasoning = (String) e.get("reasoning");
                    if (reasoning != null && reasoning.startsWith("abandoned: EV below threshold")) {
                        r.stoppingRuleActivations++;
                    }
                }
            }
            // outcomes are read back from the database of record, not the agent's word
            RecoveryCase updated = caseRepository.findById(c.getId()).orElseThrow();
            r.actionsTaken += ((List<String>) response.getOrDefault("actions", List.of())).size();
            r.paymentAttempts += updated.getAttempts();
            r.contactsMade += updated.getContactsMade();
            boolean recovered = updated.getStatus() == CaseStatus.RECOVERED;
            if (recovered) {
                r.casesRecovered++;
                r.recoveredPaise += updated.getRecoveredPaise();
            }

            int third = Math.min(index / 100, 2);
            thirdCases[third]++;
            thirdContacts[third] += updated.getContactsMade();
            if (recovered) {
                thirdRecovered[third]++;
                thirdPaise[third] += updated.getRecoveredPaise();
            }
            String cause = com.recovery.razorpay.CauseMap.diagnose(updated.getErrorReason());
            long[] agg = causeAgg.computeIfAbsent(cause, k -> new long[4]);
            agg[0]++;
            if (recovered) { agg[1]++; agg[2] += updated.getRecoveredPaise(); }
            agg[3] += updated.getContactsMade();
            index++;
        }

        r.learningCurve = new java.util.ArrayList<>();
        for (int t = 0; t < 3; t++) {
            Map<String, Object> row = new java.util.LinkedHashMap<>();
            row.put("cases", "%d-%d".formatted(t * 100 + 1, t * 100 + thirdCases[t]));
            row.put("recovered_cases", thirdRecovered[t]);
            row.put("recovered_paise", thirdPaise[t]);
            row.put("contacts", thirdContacts[t]);
            row.put("contacts_per_10k", thirdPaise[t] == 0 ? 0.0
                    : Math.round(100.0 * thirdContacts[t] / (thirdPaise[t] / 1_000_000.0)) / 100.0);
            r.learningCurve.add(row);
        }
        r.perCause = new java.util.LinkedHashMap<>();
        causeAgg.forEach((cause, agg) -> {
            Map<String, Object> row = new java.util.LinkedHashMap<>();
            row.put("cases", agg[0]);
            row.put("recovered_cases", agg[1]);
            row.put("recovery_rate_pct", Math.round(1000.0 * agg[1] / agg[0]) / 10.0);
            row.put("recovered_paise", agg[2]);
            row.put("contacts", agg[3]);
            r.perCause.put(cause, row);
        });
        return r;
    }

    // ------------------------------------------------------------------
    private StrategyResult runOracle() {
        List<RecoveryCase> cases = caseLoader.loadFresh();
        StrategyResult r = new StrategyResult("ORACLE");
        for (RecoveryCase c : cases) {
            Object recoversIf = c.getGroundTruth() == null ? null : c.getGroundTruth().get("recovers_if");
            if (recoversIf == null) {
                close(c, "oracle: unrecoverable");
                continue;
            }
            RecoveryAction action = RecoveryAction.fromWire((String) recoversIf);
            if (action.isCustomerContact() && isOptedOut(c)) {
                close(c, "oracle: recovery needs contact but customer opted out");
                continue;
            }
            GatewayResult result = gateway.execute(c, action);
            r.actionsTaken++;
            if (action.isCustomerContact()) {
                r.contactsMade++;
                c.setContactsMade(1);
            } else {
                r.paymentAttempts++;
                c.setAttempts(1);
            }
            decisionLogger.logAction(c.getId(), action.wire(),
                    "oracle: ground truth says this action recovers",
                    result.success() ? "RECOVERED" : "FAILED", 1);
            if (result.success()) {
                recover(c, r);
            } else {
                close(c, "oracle: action failed unexpectedly");
            }
        }
        return r;
    }

    // ------------------------------------------------------------------
    private boolean isOptedOut(RecoveryCase c) {
        return c.getCustomerHistory() != null
                && Boolean.TRUE.equals(c.getCustomerHistory().get("opted_out"));
    }

    private void recover(RecoveryCase c, StrategyResult r) {
        c.setStatus(CaseStatus.RECOVERED);
        c.setRecoveredPaise(c.getAmountPaise());
        caseRepository.save(c);
        r.casesRecovered++;
        r.recoveredPaise += c.getAmountPaise();
    }

    private void close(RecoveryCase c, String reason) {
        c.setStatus(CaseStatus.CLOSED);
        caseRepository.save(c);
        decisionLogger.log(c.getId(), "close", null, "close_case", reason,
                null, false, null, "CLOSED", null);
    }

    // ------------------------------------------------------------------
    private void writeResultsMarkdown(Map<String, StrategyResult> results,
                                      long oracleRecovered, long totalAtRisk, String runId) {
        StringBuilder md = new StringBuilder();
        md.append("# Batch evaluation results\n\n");
        md.append("Run: `").append(runId).append("` — 300 synthetic cases (seed 42), SimulatedGateway.\n\n");
        md.append(String.format("Total at risk: **₹%,.0f**%n%n", totalAtRisk / 100.0));
        md.append("| Strategy | Recovered ₹ | % of oracle | Cases recovered | Contacts | Contacts per ₹10k | Payment attempts | Stopping-rule activations | Escalations |\n");
        md.append("|---|---|---|---|---|---|---|---|---|\n");
        for (StrategyResult r : results.values()) {
            double pct = oracleRecovered == 0 ? 0 : 100.0 * r.recoveredPaise / oracleRecovered;
            md.append(String.format("| %s | ₹%,.0f | %.1f%% | %d | %d | %.2f | %d | %d | %d |%n",
                    r.strategy, r.recoveredPaise / 100.0, pct, r.casesRecovered,
                    r.contactsMade, r.contactsPer10kRecovered(), r.paymentAttempts,
                    r.stoppingRuleActivations, r.escalations));
        }
        StrategyResult agent = results.get("AGENT");
        if (agent != null && agent.learningCurve != null) {
            md.append("\n## Learning curve (AGENT, Beta-Bernoulli)\n\n");
            md.append("| Cases | Recovered | Recovered ₹ | Contacts | Contacts per ₹10k |\n");
            md.append("|---|---|---|---|---|\n");
            for (Map<String, Object> row : agent.learningCurve) {
                md.append(String.format("| %s | %s | ₹%,.0f | %s | %s |%n",
                        row.get("cases"), row.get("recovered_cases"),
                        ((Number) row.get("recovered_paise")).longValue() / 100.0,
                        row.get("contacts"), row.get("contacts_per_10k")));
            }
        }
        if (agent != null && agent.perCause != null) {
            md.append("\n## Per-cause breakdown (AGENT)\n\n");
            md.append("| Cause | Cases | Recovered | Rate | Recovered ₹ | Contacts |\n");
            md.append("|---|---|---|---|---|---|\n");
            agent.perCause.forEach((cause, row) -> md.append(String.format(
                    "| %s | %s | %s | %s%% | ₹%,.0f | %s |%n",
                    cause, row.get("cases"), row.get("recovered_cases"),
                    row.get("recovery_rate_pct"),
                    ((Number) row.get("recovered_paise")).longValue() / 100.0,
                    row.get("contacts"))));
        }
        if (agent == null) {
            md.append("\n_AGENT row appears when the agent service is running "
                    + "(--recovery.batch.include-agent=true)._\n");
        }
        try {
            Path out = Path.of(resultsFile);
            if (out.getParent() != null) {
                Files.createDirectories(out.getParent());
            }
            Files.writeString(out, md.toString());
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to write " + resultsFile, e);
        }
    }
}
