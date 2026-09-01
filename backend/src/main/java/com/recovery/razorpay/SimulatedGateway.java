package com.recovery.razorpay;

import com.recovery.domain.RecoveryCase;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * Deterministic simulator used for batch evaluation.
 *
 * A synthetic case carries ground_truth.recovers_if — the single action that
 * would recover the payment (null = unrecoverable). An action succeeds if and
 * only if it equals recovers_if. Time is collapsed: a scheduled 24h retry
 * resolves immediately.
 *
 * Determinism is deliberate: the same cases.jsonl always produces the same
 * batch numbers, so strategy comparisons are reproducible.
 */
@Component
public class SimulatedGateway implements RazorpayGateway {

    @Override
    public GatewayResult execute(RecoveryCase recoveryCase, RecoveryAction action) {
        Map<String, Object> groundTruth = recoveryCase.getGroundTruth();
        if (groundTruth == null) {
            return GatewayResult.failed("simulated: no ground truth on case");
        }

        Object recoversIf = groundTruth.get("recovers_if");
        if (recoversIf == null) {
            return GatewayResult.failed("simulated: case is unrecoverable");
        }

        if (action.wire().equals(recoversIf)) {
            return GatewayResult.ok("simulated: " + action.wire() + " recovered payment");
        }
        return GatewayResult.failed(
                "simulated: " + action.wire() + " did not recover (needs " + recoversIf + ")");
    }
}
