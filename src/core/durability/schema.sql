-- SPDX-License-Identifier: Apache-2.0
-- Durability schema (specs/005-durable-execution/data-model.md,
-- specs/014-dispatched-resume/data-model.md).
--
-- Four tables, one idea each: where a run got to, who owns it, what it was in the
-- middle of, and what its subject consented to. Nothing here holds credential material
-- — checkpoints hold state (Principle IV), and that is enforced above this layer as
-- well as absent from it.

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
    written_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- How many times this run has been revived (014, D3).
    --
    -- On the CHECKPOINT because it must survive the disruption it counts. Memory resets
    -- with the allocation, and the suspended-run index row is deleted on dispatch —
    -- which is exactly the moment the count matters. This row is the one durable record
    -- with the run's own lifetime.
    --
    -- Additive and defaulted, so every checkpoint written before this column existed
    -- reads back as "never resumed", which is true of all of them.
    resume_count   INTEGER     NOT NULL DEFAULT 0
);

-- THE COLUMN ABOVE, FOR DATABASES THAT ALREADY HAVE THIS TABLE.
--
-- `CREATE TABLE IF NOT EXISTS` is a no-op against an existing table — it does not
-- reconcile columns — so on any enclave brought up before 014 the definition above is
-- never read and `resume_count` would simply not exist. Every `save()` would then fail on
-- an unknown column, which is the whole durability layer down, on a running enclave, from
-- a file that looks like it declares the column.
--
-- **This is the first additive column in the repository's history** — `grep -rn "ALTER
-- TABLE" src/` found nothing before this line — so there was no precedent to copy and no
-- migration runner to reach for. `ADD COLUMN IF NOT EXISTS` is idempotent, so this file
-- stays safe to re-apply, which is the property `migrate()` depends on. The declaration
-- above is kept for fresh databases: it is where someone reads what the table IS, and a
-- table whose shape must be assembled from a CREATE plus a trailing patch list is one
-- nobody can read.
ALTER TABLE checkpoints ADD COLUMN IF NOT EXISTS resume_count INTEGER NOT NULL DEFAULT 0;

-- The durable half of ADR-0026, built nine features late (014, research F1).
--
-- ADR-0026's own words were "Durable consent. Referenced by a checkpoint via grant_id
-- only" — and the referenced-by half shipped while the durable half did not.
-- `issue_grant` built a grant in memory, nothing persisted it, and the dispatched
-- entrypoint never issued one at all. So `checkpoints.grant_id` referenced nothing, and
-- worse, referenced nothing WRONGLY: the entrypoint wrote the 15-minute task
-- credential's id into the column meant for hours-long consent. Resume's first act is
-- `grant.assert_live(clock)`, so until this table existed, consent expiry was
-- unevaluable on the dispatched path — the requirement was written, and nothing could
-- check it.
--
-- CONSENT METADATA, ZERO CREDENTIAL MATERIAL. Subject, definition, scope, issued,
-- expires. No token, no password, no lease, no credential id. `DelegationGrant` enforces
-- this structurally by having no field for it; this table is the same discipline in the
-- store, and the 005 no-secret conformance sweep extends here verbatim (FR-012) — as a
-- row, not as a remark.
--
-- WRITTEN ONCE AT ISSUANCE, NEVER UPDATED. A grant's terms do not change; a new consent
-- is a new grant. Expiry is read from the record rather than enforced by mutating it,
-- which is why there is no `revoked_at` and no update path in the provider.
CREATE TABLE IF NOT EXISTS grants (
    grant_id            TEXT PRIMARY KEY,
    subject_user_id     TEXT        NOT NULL,
    agent_definition_id TEXT        NOT NULL,
    -- AuthorityScope's two frozensets, written as SORTED lists so the stored jsonb is
    -- deterministic and two saves of one grant are byte-identical (analyze M2).
    requested_scope     JSONB       NOT NULL DEFAULT '{}'::jsonb,
    issued_at           TIMESTAMPTZ NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL
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
