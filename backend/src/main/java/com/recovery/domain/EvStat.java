package com.recovery.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;

import java.io.Serializable;
import java.util.Objects;

/**
 * Beta-Bernoulli learning table: P(recovery | cause, action) ~ Beta(alpha, beta).
 * alpha counts successes, beta counts failures; the posterior mean alpha/(alpha+beta)
 * is used as the probability inside the expected-value calculation.
 */
@Entity
@Table(name = "ev_stats")
@IdClass(EvStat.Key.class)
public class EvStat {

    @Id
    private String cause;

    @Id
    private String action;

    @Column(nullable = false)
    private int alpha;

    @Column(nullable = false)
    private int beta;

    public EvStat() {
    }

    public EvStat(String cause, String action, int alpha, int beta) {
        this.cause = cause;
        this.action = action;
        this.alpha = alpha;
        this.beta = beta;
    }

    public String getCause() { return cause; }
    public void setCause(String cause) { this.cause = cause; }

    public String getAction() { return action; }
    public void setAction(String action) { this.action = action; }

    public int getAlpha() { return alpha; }
    public void setAlpha(int alpha) { this.alpha = alpha; }

    public int getBeta() { return beta; }
    public void setBeta(int beta) { this.beta = beta; }

    public double posteriorMean() {
        return (double) alpha / (alpha + beta);
    }

    public static class Key implements Serializable {
        private String cause;
        private String action;

        public Key() {
        }

        public Key(String cause, String action) {
            this.cause = cause;
            this.action = action;
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof Key key)) return false;
            return Objects.equals(cause, key.cause) && Objects.equals(action, key.action);
        }

        @Override
        public int hashCode() {
            return Objects.hash(cause, action);
        }
    }
}
