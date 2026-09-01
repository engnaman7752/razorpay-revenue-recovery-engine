package com.recovery.tools;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;

/**
 * Every request under /internal/tools/** must carry the shared secret in
 * X-Agent-Secret. Constant-time comparison; 401 on mismatch. These endpoints
 * are also excluded from public CORS (no CORS mapping covers /internal/**).
 */
@Component
public class ToolAuthFilter extends OncePerRequestFilter {

    @Value("${recovery.agent-shared-secret}")
    private String agentSharedSecret;

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/internal/tools/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String provided = request.getHeader("X-Agent-Secret");
        if (provided == null || !MessageDigest.isEqual(
                provided.getBytes(StandardCharsets.UTF_8),
                agentSharedSecret.getBytes(StandardCharsets.UTF_8))) {
            response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
            response.setContentType("application/json");
            response.getWriter().write("{\"error\":\"invalid or missing X-Agent-Secret\"}");
            return;
        }
        chain.doFilter(request, response);
    }
}
