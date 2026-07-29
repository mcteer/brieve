-- SPDX-License-Identifier: Apache-2.0
-- Threads: a readable view over what the audit trail already records
-- (specs/012-conversational-portal/data-model.md, ADR-0051).
--
-- Nothing here is read by resume, so all of it is droppable — the same property
-- src/core/runs/ protects. What is NOT droppable is the trail, which is the point: these
-- tables can be deleted, per-thread by their owner, precisely because deleting a reading
-- of a record removes no record.

-- A conversation's spine.
--
-- Hard-deleted by its owner. A soft-delete column was considered and rejected: retaining
-- every message in a table whose whole justification for being deletable is that the
-- trail is the record would be the worst of both.
CREATE TABLE IF NOT EXISTS threads (
    thread_id       TEXT PRIMARY KEY,
    -- The join to the trail. One correlation id per thread: every turn event, and every
    -- run the thread starts, chains under it or references it.
    correlation_id  TEXT        NOT NULL UNIQUE,
    subject_user_id TEXT        NOT NULL,
    tenant_id       TEXT        NOT NULL,
    -- Null until the first accepted turn sets it, once. No operation renames it, so it
    -- cannot drift from what actually happened.
    title           TEXT,
    created_at      TIMESTAMPTZ NOT NULL
);

-- Listing (keyset, newest first) AND one leg of the rate window.
--
-- Both uses want the same three columns in the same order, which is why creation counting
-- costs nothing extra: the index the listing already needed serves it.
CREATE INDEX IF NOT EXISTS threads_by_subject
    ON threads (tenant_id, subject_user_id, created_at DESC, thread_id DESC);

-- One accepted exchange.
--
-- Insert-only; rows die only with their thread. `tenant_id` and `subject_user_id` are
-- denormalized from the thread deliberately — the rate window counts a PERSON's acts
-- across every thread they have, and a query that joined through a single thread would
-- bound each thread separately, which is thirty threads times thirty turns.
CREATE TABLE IF NOT EXISTS thread_turns (
    turn_id             TEXT PRIMARY KEY,
    thread_id           TEXT        NOT NULL REFERENCES threads (thread_id) ON DELETE CASCADE,
    tenant_id           TEXT        NOT NULL,
    subject_user_id     TEXT        NOT NULL,
    -- Dense per-thread ordering, assigned under the thread's row lock. Two browser tabs
    -- sending at once cannot interleave into ambiguity.
    seq                 INTEGER     NOT NULL,
    message             TEXT        NOT NULL,
    disposition         TEXT        NOT NULL,
    reason              TEXT,
    run_id              TEXT,
    agent_definition_id TEXT,
    -- Comma-joined, ordered newest-first. Text rather than an array so the in-memory and
    -- Postgres stores agree on shape without a driver-specific type.
    context_run_ids     TEXT        NOT NULL DEFAULT '',
    context_dropped     TEXT        NOT NULL DEFAULT '',
    created_at          TIMESTAMPTZ NOT NULL,
    UNIQUE (thread_id, seq)
);

-- Reading a thread: its turns in order.
CREATE INDEX IF NOT EXISTS thread_turns_by_thread ON thread_turns (thread_id, seq);

-- The other leg of the rate window. The window is the SUM of this count and the one over
-- `threads`, because creations write no turn row — a window counting only this table
-- would read zero while a subject created ten thousand empty threads.
CREATE INDEX IF NOT EXISTS thread_turns_by_subject
    ON thread_turns (tenant_id, subject_user_id, created_at);

-- What a dispatched run reads at start.
--
-- Written by the turn operation BEFORE dispatch; read by the run under its own workload
-- credentials. Deliberately not passed through the scheduler: Nomad dispatch metadata
-- lands in the jobspec and the allocation environment, visible to anyone with scheduler
-- access and outside the tenant-scoped read path — and a person's free text must not go
-- there.
--
-- NOT deleted with the thread. The run outlives the view (FR-010d), and a run whose input
-- vanished mid-flight would be a run nobody could explain.
CREATE TABLE IF NOT EXISTS run_inputs (
    run_id          TEXT PRIMARY KEY,
    message         TEXT        NOT NULL,
    -- References, not copies: resolved to the recorded bytes at run start.
    context_run_ids TEXT        NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL
);
