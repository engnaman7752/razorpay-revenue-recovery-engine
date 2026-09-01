package com.recovery.domain;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface RecoveryCaseRepository extends JpaRepository<RecoveryCase, UUID> {

    Optional<RecoveryCase> findByRazorpayOrderId(String razorpayOrderId);

    Optional<RecoveryCase> findByRazorpayPaymentId(String razorpayPaymentId);

    List<RecoveryCase> findByStatus(CaseStatus status);

    List<RecoveryCase> findBySource(String source);

    long countByStatus(CaseStatus status);
}
