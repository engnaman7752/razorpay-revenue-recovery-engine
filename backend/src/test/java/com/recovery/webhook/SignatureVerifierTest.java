package com.recovery.webhook;

import org.junit.jupiter.api.Test;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.util.HexFormat;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SignatureVerifierTest {

    private static final String SECRET = "whsec_test_secret";
    private static final byte[] BODY =
            "{\"event\":\"payment.failed\",\"payload\":{\"payment\":{\"entity\":{\"id\":\"pay_1\"}}}}"
                    .getBytes(StandardCharsets.UTF_8);

    private static String sign(byte[] body, String secret) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        return HexFormat.of().formatHex(mac.doFinal(body));
    }

    @Test
    void validSignaturePasses() throws Exception {
        assertTrue(SignatureVerifier.verify(BODY, sign(BODY, SECRET), SECRET));
    }

    @Test
    void tamperedBodyFails() throws Exception {
        String signature = sign(BODY, SECRET);
        byte[] tampered = new String(BODY, StandardCharsets.UTF_8)
                .replace("pay_1", "pay_2").getBytes(StandardCharsets.UTF_8);
        assertFalse(SignatureVerifier.verify(tampered, signature, SECRET));
    }

    @Test
    void reserializedJsonFails() throws Exception {
        // same JSON, different whitespace: must fail — verification is over raw bytes
        String signature = sign(BODY, SECRET);
        byte[] pretty = "{ \"event\": \"payment.failed\", \"payload\": {\"payment\": {\"entity\": {\"id\": \"pay_1\"}}} }"
                .getBytes(StandardCharsets.UTF_8);
        assertFalse(SignatureVerifier.verify(pretty, signature, SECRET));
    }

    @Test
    void wrongSecretFails() throws Exception {
        assertFalse(SignatureVerifier.verify(BODY, sign(BODY, "other_secret"), SECRET));
    }

    @Test
    void nullsAndBlanksFailClosed() {
        assertFalse(SignatureVerifier.verify(null, "abc", SECRET));
        assertFalse(SignatureVerifier.verify(BODY, null, SECRET));
        assertFalse(SignatureVerifier.verify(BODY, "abc", ""));
    }
}
