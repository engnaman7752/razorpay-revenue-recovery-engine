package com.recovery.domain;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;

public interface BatchResultRepository extends JpaRepository<BatchResult, Long> {

    List<BatchResult> findByRunIdOrderById(String runId);

    Optional<BatchResult> findFirstByOrderByIdDesc();
}
