package com.recovery.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.Map;
import java.util.UUID;

@Entity
@Table(name = "decision_log")
public class DecisionLog {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "case_id", nullable = false)
    private UUID caseId;

    @Column(nullable = false)
    private OffsetDateTime ts = OffsetDateTime.now();

    @Column(nullable = false)
    private String node;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "inputs_seen", columnDefinition = "jsonb")
    private Map<String, Object> inputsSeen;

    @Column(name = "action_chosen")
    private String actionChosen;

    @Column(columnDefinition = "text")
    private String reasoning;

    @Column(name = "ev_score")
    private BigDecimal evScore;

    @Column(nullable = false)
    private boolean blocked = false;

    @Column(name = "block_reason")
    private String blockReason;

    private String outcome;

    @Column(name = "attempt_number")
    private Integer attemptNumber;

    // --- getters and setters ---

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public UUID getCaseId() { return caseId; }
    public void setCaseId(UUID caseId) { this.caseId = caseId; }

    public OffsetDateTime getTs() { return ts; }
    public void setTs(OffsetDateTime ts) { this.ts = ts; }

    public String getNode() { return node; }
    public void setNode(String node) { this.node = node; }

    public Map<String, Object> getInputsSeen() { return inputsSeen; }
    public void setInputsSeen(Map<String, Object> inputsSeen) { this.inputsSeen = inputsSeen; }

    public String getActionChosen() { return actionChosen; }
    public void setActionChosen(String actionChosen) { this.actionChosen = actionChosen; }

    public String getReasoning() { return reasoning; }
    public void setReasoning(String reasoning) { this.reasoning = reasoning; }

    public BigDecimal getEvScore() { return evScore; }
    public void setEvScore(BigDecimal evScore) { this.evScore = evScore; }

    public boolean isBlocked() { return blocked; }
    public void setBlocked(boolean blocked) { this.blocked = blocked; }

    public String getBlockReason() { return blockReason; }
    public void setBlockReason(String blockReason) { this.blockReason = blockReason; }

    public String getOutcome() { return outcome; }
    public void setOutcome(String outcome) { this.outcome = outcome; }

    public Integer getAttemptNumber() { return attemptNumber; }
    public void setAttemptNumber(Integer attemptNumber) { this.attemptNumber = attemptNumber; }
}
