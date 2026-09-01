package com.recovery.domain;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface EvStatRepository extends JpaRepository<EvStat, EvStat.Key> {

    Optional<EvStat> findByCauseAndAction(String cause, String action);
}
