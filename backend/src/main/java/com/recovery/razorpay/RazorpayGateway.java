package com.recovery.razorpay;

import com.recovery.domain.RecoveryCase;

/**
 * Boundary to Razorpay. Two implementations selected by GATEWAY_MODE:
 *  - SimulatedGateway  (batch evaluation; resolves against ground_truth)
 *  - LiveRazorpayGateway (Phase 6; real test-mode API calls)
 */
public interface RazorpayGateway {

    GatewayResult execute(RecoveryCase recoveryCase, RecoveryAction action);
}
