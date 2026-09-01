-- Summary metrics per batch strategy run, read by GET /api/metrics.
CREATE TABLE batch_result (
    id       BIGSERIAL PRIMARY KEY,
    run_id   TEXT NOT NULL,
    strategy TEXT NOT NULL,   -- DO_NOTHING | NAIVE | AGENT | ORACLE
    metrics  JSONB NOT NULL,
    ts       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_batch_run ON batch_result (run_id);
