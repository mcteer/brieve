-- SPDX-License-Identifier: Apache-2.0
-- Durability schema (specs/005-durable-execution/data-model.md).
--
-- Three tables, one idea each: where a run got to, who owns it, and what it was in
-- the middle of. Nothing here holds credential material — checkpoints hold state
-- (Principle IV), and that is enforced above this layer as well as absent from it.

CREATE TABLE IF NOT EXISTS checkpoints (
    blob_id        TEXT PRIMARY KEY,
    payload        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    correlation_id TEXT        NOT NULL DEFAULT '',
    grant_id       TEXT        NOT NULL DEFAULT '',
    step_index     INTEGER     NOT NULL DEFAULT 0,
    written_by     TEXT        NOT NULL DEFAULT '',
    -- Terminal state lives on the row because a resuming process has only this row.
    run_state      TEXT,
    stop_reason    TEXT,
    written_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One live lease per run. Acquisition is a single conditional upsert so a resumed
-- run supersedes a zombie atomically — fencing is then an identity comparison
-- rather than a race (FR-009).
CREATE TABLE IF NOT EXISTS run_leases (
    run_id          TEXT PRIMARY KEY,
    holder_identity TEXT        NOT NULL,
    acquired_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The bracket. A row in intents with no matching row in results is precisely the
-- interrupted case resume must resolve by observation.
CREATE TABLE IF NOT EXISTS intents (
    run_id          TEXT        NOT NULL,
    idempotency_key TEXT        NOT NULL,
    step_index      INTEGER     NOT NULL,
    tool_name       TEXT        NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (run_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS results (
    run_id          TEXT        NOT NULL,
    idempotency_key TEXT        NOT NULL,
    step_index      INTEGER     NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (run_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS intents_by_run ON intents (run_id);
