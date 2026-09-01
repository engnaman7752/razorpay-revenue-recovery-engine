package com.recovery.razorpay;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

/** Selects which RazorpayGateway implementation the tool endpoints use.
 * GATEWAY_MODE=live -> real test-mode API; anything else -> simulator.
 * (BatchRunner always injects SimulatedGateway directly, whatever the mode.) */
@Configuration
public class GatewayConfig {

    @Bean
    @Primary
    public RazorpayGateway activeGateway(SimulatedGateway simulated, LiveRazorpayGateway live,
                                         @Value("${recovery.gateway-mode:simulated}") String mode) {
        return "live".equalsIgnoreCase(mode) ? live : simulated;
    }
}
