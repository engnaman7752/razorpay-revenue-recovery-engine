package com.recovery.webhook;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * Razorpay webhook signature check: X-Razorpay-Signature must equal the
 * hex HMAC-SHA256 of the RAW request body bytes under the webhook secret.
 *
 * The RAW bytes matter: re-serializing the JSON (key order, whitespace,
 * unicode escapes) changes the digest and breaks verification. Constant-time
 * comparison via MessageDigest.isEqual.
 */
public final class SignatureVerifier {

    private SignatureVerifier() {
    }

    public static boolean verify(byte[] rawBody, String signatureHex, String secret) {
        if (rawBody == null || signatureHex == null || secret == null || secret.isBlank()) {
            return false;
        }
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] expected = hex(mac.doFinal(rawBody)).getBytes(StandardCharsets.UTF_8);
            byte[] provided = signatureHex.trim().toLowerCase().getBytes(StandardCharsets.UTF_8);
            return MessageDigest.isEqual(expected, provided);
        } catch (Exception e) {
            return false;
        }
    }

    private static String hex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(Character.forDigit((b >> 4) & 0xF, 16))
              .append(Character.forDigit(b & 0xF, 16));
        }
        return sb.toString();
    }
}
