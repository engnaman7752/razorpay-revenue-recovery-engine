package com.recovery.domain;

import org.springframework.data.jpa.repository.JpaRepository;

import java.time.OffsetDateTime;
import java.util.List;

public interface ScheduledRetryRepository extends JpaRepository<ScheduledRetry, Long> {

    List<ScheduledRetry> findByExecutedFalseAndDueAtBefore(OffsetDateTime now);
}
