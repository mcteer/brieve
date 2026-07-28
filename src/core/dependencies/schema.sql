-- SPDX-License-Identifier: Apache-2.0
-- Dependency health and suspension (specs/009-mcp-surface/data-model.md).
--
-- Operational state, not evidence. The evidence role holds no grant on either table:
-- widening a SELECT-only credential to cover "things in the same database" is how it
-- quietly becomes a general reader.

CREATE TABLE IF NOT EXISTS dependency_health (
    product               TEXT PRIMARY KEY,
    state                 TEXT        NOT NULL,
    -- So staleness is visible rather than inferred. A record old enough to distrust reads
    -- as UNKNOWN, which is treated as unhealthy — the same posture as never having checked.
    checked_at            TIMESTAMPTZ NOT NULL,
    -- Recovery is hysteretic and failure is not. One failure marks unhealthy; several
    -- consecutive successes mark healthy. Asymmetric on purpose: marking unhealthy fast
    -- costs a suspension the sweeper resolves, while marking healthy fast resumes every
    -- waiting run into a product that fails again, burning each run's duration budget.
    consecutive_successes INTEGER     NOT NULL DEFAULT 0,
    detail                TEXT        NOT NULL DEFAULT ''
);

-- The sweeper's candidate list. An INDEX over the checkpoint, never a second record of
-- state: 005's checkpoint run_state is authoritative and says SUSPENDED too.
--
-- Two stores that can disagree fail silently in both directions — a run suspended in its
-- checkpoint but absent here is invisible to the sweeper forever, which presents exactly
-- like the hang ADR-0049 exists to prevent; a row here whose checkpoint has since reached
-- a terminal state has the sweeper resuming a finished run. So both writes happen in one
-- transaction and the sweeper re-reads the checkpoint before resuming.
CREATE TABLE IF NOT EXISTS suspended_runs (
    run_id         TEXT PRIMARY KEY,
    correlation_id TEXT        NOT NULL,
    -- Named, so the sweeper knows what to watch. Required at the point of suspending:
    -- a suspension nobody can match to a recovery never resumes.
    awaiting       TEXT        NOT NULL,
    suspended_at   TIMESTAMPTZ NOT NULL,
    step_index     INTEGER     NOT NULL
);

-- The sweeper asks "what is waiting on this product", not "which runs are suspended", so
-- the index leads with the dependency rather than making it a scan.
CREATE INDEX IF NOT EXISTS suspended_by_dependency ON suspended_runs (awaiting);
