package com.recovery.tools;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Supplier;

/**
 * The agent's six hands. Authenticated by ToolAuthFilter (X-Agent-Secret),
 * excluded from public CORS, every call logged to decision_log by the services.
 */
@RestController
@RequestMapping("/internal/tools")
public class ToolController {

    private final RetryPaymentTool retryPaymentTool;
    private final ScheduleRetryTool scheduleRetryTool;
    private final PaymentLinkTool paymentLinkTool;
    private final ReminderTool reminderTool;
    private final EscalateTool escalateTool;
    private final CloseCaseTool closeCaseTool;

    private final Map<String, Map<String, Object>> idempotencyCache = new ConcurrentHashMap<>();

    public ToolController(RetryPaymentTool retryPaymentTool, ScheduleRetryTool scheduleRetryTool,
                          PaymentLinkTool paymentLinkTool, ReminderTool reminderTool,
                          EscalateTool escalateTool, CloseCaseTool closeCaseTool) {
        this.retryPaymentTool = retryPaymentTool;
        this.scheduleRetryTool = scheduleRetryTool;
        this.paymentLinkTool = paymentLinkTool;
        this.reminderTool = reminderTool;
        this.escalateTool = escalateTool;
        this.closeCaseTool = closeCaseTool;
    }

    private Map<String, Object> withIdempotency(HttpServletRequest request,
                                                Supplier<Map<String, Object>> action) {
        String key = request != null ? request.getHeader("X-Idempotency-Key") : null;
        if (key != null) {
            Map<String, Object> cached = idempotencyCache.get(key);
            if (cached != null) return cached;
        }
        Map<String, Object> result = action.get();
        if (key != null && result != null) idempotencyCache.put(key, result);
        return result;
    }

    @PostMapping("/retry-payment")
    public Map<String, Object> retryPayment(HttpServletRequest request, @RequestBody Map<String, Object> body) {
        return withIdempotency(request, () -> retryPaymentTool.run((String) body.get("case_id")));
    }

    @PostMapping("/schedule-retry")
    public Map<String, Object> scheduleRetry(@RequestBody Map<String, Object> body) {
        int delayHours = body.get("delay_hours") == null ? 24
                : ((Number) body.get("delay_hours")).intValue();
        return scheduleRetryTool.run((String) body.get("case_id"), delayHours);
    }

    @PostMapping("/create-payment-link")
    public Map<String, Object> createPaymentLink(HttpServletRequest request, @RequestBody Map<String, Object> body) {
        return withIdempotency(request, () -> paymentLinkTool.run((String) body.get("case_id")));
    }

    @PostMapping("/send-reminder")
    public Map<String, Object> sendReminder(HttpServletRequest request, @RequestBody Map<String, Object> body) {
        String channel = body.get("channel") == null ? "email" : (String) body.get("channel");
        return withIdempotency(request, () -> reminderTool.run((String) body.get("case_id"), channel));
    }

    @PostMapping("/escalate")
    public Map<String, Object> escalate(@RequestBody Map<String, Object> body) {
        return escalateTool.run((String) body.get("case_id"), (String) body.get("reason"));
    }

    @PostMapping("/close-case")
    public Map<String, Object> closeCase(@RequestBody Map<String, Object> body) {
        return closeCaseTool.run((String) body.get("case_id"), (String) body.get("reason"));
    }
}
