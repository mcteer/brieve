-- SPDX-License-Identifier: Apache-2.0
-- Operational records about runs (specs/011-api-operations/data-model.md).
--
-- Two tables, one idea each: what a person has started, and what they asked to change.
-- Neither is read by resume, and that is the property that keeps them droppable —
-- see src/core/runs/__init__.py.

-- What has this person started.
--
-- The question `checkpoints` cannot answer, because 005 built it for resume and resume
-- never needed a subject. Insert-only: state lives on the checkpoint, which stays
-- authoritative, and an index that carried state would be the second writer the
-- checkpoint's row lock exists to prevent.
CREATE TABLE IF NOT EXISTS run_index (
    run_id              TEXT PRIMARY KEY,
    correlation_id      TEXT        NOT NULL,
    -- The two columns the whole table exists for.
    subject_user_id     TEXT        NOT NULL,
    tenant_id           TEXT        NOT NULL,
    agent_definition_id TEXT        NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The list operation's exact query shape, so the tenant filter is the ACCESS PATH rather
-- than a predicate applied after rows are read. A boundary enforced by an index is a
-- boundary the planner cannot decide to check late.
CREATE INDEX IF NOT EXISTS run_index_by_owner
    ON run_index (tenant_id, subject_user_id, created_at DESC, run_id DESC);

-- A submitted authority change, so its outcome can be collected.
--
-- 008 returned the accessor and stored nothing, which is the defect US1 closes. The
-- record is the AUTHORIZATION, not a cache: Vault's status endpoint answers anyone
-- presenting an accessor, so without a requester and a tenant to compare against, the
-- accessor is a bearer capability that crosses tenants.
CREATE TABLE IF NOT EXISTS authority_change_requests (
    accessor     TEXT PRIMARY KEY,
    requester    TEXT        NOT NULL,
    tenant_id    TEXT        NOT NULL,
    claim_name   TEXT        NOT NULL,
    claim_value  TEXT        NOT NULL,
    role         TEXT        NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS change_requests_by_requester
    ON authority_change_requests (tenant_id, requester, submitted_at DESC);
