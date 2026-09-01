package com.recovery.razorpay;

/** Outcome of executing one action against the (real or simulated) gateway.
 * pending = the action was initiated but resolves later via webhook (live mode). */
public record GatewayResult(boolean success, boolean pending, String detail) {

    public static GatewayResult ok(String detail) {
        return new GatewayResult(true, false, detail);
    }

    public static GatewayResult failed(String detail) {
        return new GatewayResult(false, false, detail);
    }

    public static GatewayResult pending(String detail) {
        return new GatewayResult(false, true, detail);
    }
}
