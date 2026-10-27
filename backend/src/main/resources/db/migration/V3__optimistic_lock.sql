-- Optimistic locking: prevents concurrent webhook + agent updates from overwriting each other.
ALTER TABLE recovery_case ADD COLUMN IF NOT EXISTS version BIGINT NOT NULL DEFAULT 0;
