-- Schema of record for the AI Revenue Recovery Engine.
-- Owned by Flyway; Hibernate runs in validate-only mode.

CREATE TABLE recovery_case (
    id                  UUID PRIMARY KEY,
    razorpay_order_id   TEXT,
    razorpay_payment_id TEXT,
    amount_paise        BIGINT NOT NULL,
    currency            TEXT NOT NULL DEFAULT 'INR',
    error_reason        TEXT,
    error_source        TEXT,
    diagnosis           TEXT,
    status              TEXT NOT NULL DEFAULT 'DETECTED',
    attempts            INT NOT NULL DEFAULT 0,
    contacts_made       INT NOT NULL DEFAULT 0,
    recovered_paise     BIGINT NOT NULL DEFAULT 0,
    customer_id         TEXT,
    customer_history    JSONB,
    source              TEXT NOT NULL DEFAULT 'SYNTHETIC',  -- LIVE | SYNTHETIC
    ground_truth        JSONB,                              -- synthetic only
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_case_status ON recovery_case (status);
CREATE INDEX idx_case_source ON recovery_case (source);
CREATE INDEX idx_case_order  ON recovery_case (razorpay_order_id);

CREATE TABLE decision_log (
    id             BIGSERIAL PRIMARY KEY,
    case_id        UUID NOT NULL REFERENCES recovery_case (id),
    ts             TIMESTAMPTZ NOT NULL DEFAULT now(),
    node           TEXT NOT NULL,           -- diagnose | decide | guard | execute | check_outcome | close
    inputs_seen    JSONB,                   -- exact snapshot the agent saw
    action_chosen  TEXT,
    reasoning      TEXT,
    ev_score       NUMERIC,
    blocked        BOOLEAN NOT NULL DEFAULT FALSE,
    block_reason   TEXT,
    outcome        TEXT,
    attempt_number INT
);

CREATE INDEX idx_decision_case ON decision_log (case_id, ts);

-- Beta-Bernoulli learning table: P(recovery | cause, action) ~ Beta(alpha, beta)
CREATE TABLE ev_stats (
    cause  TEXT NOT NULL,
    action TEXT NOT NULL,
    alpha  INT NOT NULL,
    beta   INT NOT NULL,
    PRIMARY KEY (cause, action)
);

-- Scheduled retries picked up by RetryScheduler (@Scheduled every 60s)
CREATE TABLE scheduled_retry (
    id       BIGSERIAL PRIMARY KEY,
    case_id  UUID NOT NULL REFERENCES recovery_case (id),
    due_at   TIMESTAMPTZ NOT NULL,
    executed BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_retry_due ON scheduled_retry (executed, due_at);
