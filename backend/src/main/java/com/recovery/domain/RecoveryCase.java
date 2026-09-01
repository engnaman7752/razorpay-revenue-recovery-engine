package com.recovery.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "recovery_case")
public class RecoveryCase {

    @Id
    private UUID id;

    @Column(name = "razorpay_order_id")
    private String razorpayOrderId;

    @Column(name = "razorpay_payment_id")
    private String razorpayPaymentId;

    @Column(name = "amount_paise", nullable = false)
    private long amountPaise;

    @Column(nullable = false)
    private String currency = "INR";

    @Column(name = "error_reason")
    private String errorReason;

    @Column(name = "error_source")
    private String errorSource;

    private String diagnosis;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private CaseStatus status = CaseStatus.DETECTED;

    @Column(nullable = false)
    private int attempts = 0;

    @Column(name = "contacts_made", nullable = false)
    private int contactsMade = 0;

    @Column(name = "recovered_paise", nullable = false)
    private long recoveredPaise = 0;

    @Column(name = "customer_id")
    private String customerId;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "customer_history", columnDefinition = "jsonb")
    private Map<String, Object> customerHistory;

    @Column(nullable = false)
    private String source = "SYNTHETIC";

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "ground_truth", columnDefinition = "jsonb")
    private Map<String, Object> groundTruth;

    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt = OffsetDateTime.now();

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt = OffsetDateTime.now();

    @PreUpdate
    void onUpdate() {
        this.updatedAt = OffsetDateTime.now();
    }

    // --- getters and setters ---

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }

    public String getRazorpayOrderId() { return razorpayOrderId; }
    public void setRazorpayOrderId(String razorpayOrderId) { this.razorpayOrderId = razorpayOrderId; }

    public String getRazorpayPaymentId() { return razorpayPaymentId; }
    public void setRazorpayPaymentId(String razorpayPaymentId) { this.razorpayPaymentId = razorpayPaymentId; }

    public long getAmountPaise() { return amountPaise; }
    public void setAmountPaise(long amountPaise) { this.amountPaise = amountPaise; }

    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency; }

    public String getErrorReason() { return errorReason; }
    public void setErrorReason(String errorReason) { this.errorReason = errorReason; }

    public String getErrorSource() { return errorSource; }
    public void setErrorSource(String errorSource) { this.errorSource = errorSource; }

    public String getDiagnosis() { return diagnosis; }
    public void setDiagnosis(String diagnosis) { this.diagnosis = diagnosis; }

    public CaseStatus getStatus() { return status; }
    public void setStatus(CaseStatus status) { this.status = status; }

    public int getAttempts() { return attempts; }
    public void setAttempts(int attempts) { this.attempts = attempts; }

    public int getContactsMade() { return contactsMade; }
    public void setContactsMade(int contactsMade) { this.contactsMade = contactsMade; }

    public long getRecoveredPaise() { return recoveredPaise; }
    public void setRecoveredPaise(long recoveredPaise) { this.recoveredPaise = recoveredPaise; }

    public String getCustomerId() { return customerId; }
    public void setCustomerId(String customerId) { this.customerId = customerId; }

    public Map<String, Object> getCustomerHistory() { return customerHistory; }
    public void setCustomerHistory(Map<String, Object> customerHistory) { this.customerHistory = customerHistory; }

    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }

    public Map<String, Object> getGroundTruth() { return groundTruth; }
    public void setGroundTruth(Map<String, Object> groundTruth) { this.groundTruth = groundTruth; }

    public OffsetDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(OffsetDateTime createdAt) { this.createdAt = createdAt; }

    public OffsetDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(OffsetDateTime updatedAt) { this.updatedAt = updatedAt; }
}
