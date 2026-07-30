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
    -- Denormalized deliberately: the sweeper dispatches a resume, and a dispatch needs a
    -- subject, a tenant, and a definition. Without them here the sweeper knows a run
    -- should resume and cannot say as whom — and passing blanks would start a fresh run
    -- under a resumed run's identity, which looks like a successful resume and re-executes
    -- everything the run had already done.
    subject_user_id     TEXT   NOT NULL DEFAULT '',
    tenant_id           TEXT   NOT NULL DEFAULT '',
    agent_definition_id TEXT   NOT NULL DEFAULT '',
    -- Named, so the sweeper knows what to watch. Required at the point of suspending:
    -- a suspension nobody can match to a recovery never resumes.
    awaiting       TEXT        NOT NULL,
    suspended_at   TIMESTAMPTZ NOT NULL,
    step_index     INTEGER     NOT NULL,
    -- 014: the rest of what the run needs to be itself again.
    --
    -- The three columns above answered "as whom", which is what 009 needed to argue for.
    -- These answer "as what": the roles its claims resolved to, the packs whose observers
    -- re-observation consults, how many steps it had, and whether it invokes tools. A
    -- resume dispatched without them is a different run wearing the same identity — it
    -- refuses on `no_role_for_subject`, or re-suspends every pack-tool intent because the
    -- observer is missing, or completes trivially with its pending work silently dropped.
    --
    -- Denormalized for the same reason and with the same discipline as the identity
    -- columns: all of it is claims-derived metadata or configuration, and none of it grants
    -- anything. The roles say what the dispatching surface established; the allocation
    -- still resolves what they permit from the trust fabric.
    subject_roles  TEXT        NOT NULL DEFAULT '',
    packs          TEXT        NOT NULL DEFAULT '',
    -- Nullable, unlike the two above, because "no steps requested" and "zero steps" are
    -- different dispatches and the entrypoint distinguishes them.
    steps          INTEGER,
    invoke_tools   BOOLEAN     NOT NULL DEFAULT FALSE
);

-- The columns above, for databases that already have this table (see the durability
-- schema's note — `CREATE TABLE IF NOT EXISTS` does not reconcile columns, so on any
-- enclave brought up before 014 the definition above is never read and every one of these
-- would silently not exist).
ALTER TABLE suspended_runs ADD COLUMN IF NOT EXISTS subject_roles TEXT NOT NULL DEFAULT '';
ALTER TABLE suspended_runs ADD COLUMN IF NOT EXISTS packs TEXT NOT NULL DEFAULT '';
ALTER TABLE suspended_runs ADD COLUMN IF NOT EXISTS steps INTEGER;
ALTER TABLE suspended_runs ADD COLUMN IF NOT EXISTS invoke_tools BOOLEAN NOT NULL DEFAULT FALSE;

-- The sweeper asks "what is waiting on this product", not "which runs are suspended", so
-- the index leads with the dependency rather than making it a scan.
CREATE INDEX IF NOT EXISTS suspended_by_dependency ON suspended_runs (awaiting);
