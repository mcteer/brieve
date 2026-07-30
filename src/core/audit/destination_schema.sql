-- SPDX-License-Identifier: Apache-2.0
-- The second copy (specs/015-audit-egress/data-model.md).
--
-- Applied to a DIFFERENT store than `evidence_schema.sql`, by a different administrator,
-- and its own file for that reason: bundling it into the evidence schema would invite the
-- same-store shortcut ADR-0055 forecloses, because the two would then apply together under
-- one credential and nobody would notice the boundary had gone.
--
-- The platform holds INSERT and SELECT here (`infra/collector/roles.sql`). Everything below
-- is shaped so that append is sufficient — no row is ever updated, so no code path needs a
-- capability the platform must not have.

-- The chain entry as it exists locally, field for field.
--
-- Byte-identical to `audit_entries` in every hashed field, because a copy that differs
-- cannot be compared entry-for-entry (FR-002) and a digest-only copy detects that something
-- changed while being unable to say what — the wrong half, in ADR-0055's words.
CREATE TABLE IF NOT EXISTS shipped_entries (
    tenant_id      TEXT        NOT NULL,
    correlation_id TEXT        NOT NULL,
    seq            INTEGER     NOT NULL,
    event_type     TEXT        NOT NULL,
    timestamp      TIMESTAMPTZ NOT NULL,
    payload        JSONB       NOT NULL,
    prev_hash      TEXT        NOT NULL,
    entry_hash     TEXT        NOT NULL,
    -- The one field with no local counterpart: when the destination received it. This is
    -- what `coverage` is derived from — the range over which tamper-evidence actually
    -- holds (FR-017), which is not the same as the range the local trail covers.
    received_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- FIRST WRITE WINS, and this is the evidence posture rather than a de-duplication
    -- convenience.
    --
    -- The shipper inserts ON CONFLICT DO NOTHING, so two things follow. A crash between
    -- delivery and the watermark advance re-ships harmlessly, which is what lets the
    -- watermark advance LAST and still be correct. And an actor who rewrites a local entry
    -- and re-ships it collides with the honest original and changes nothing — the tampering
    -- is quiet at ship time and loud at reconcile time, which is the right split, because
    -- the shipper is not a judge.
    PRIMARY KEY (correlation_id, seq)
);

-- Reconciliation walks by stream; the local side is already ordered by (correlation_id, seq).
CREATE INDEX IF NOT EXISTS shipped_by_tenant ON shipped_entries (tenant_id, timestamp);

-- The platform's own claims about how long each stream was, over time.
--
-- **Append-only OBSERVATIONS, never a head row that gets updated**, and the reason is both
-- structural and evidential. Structurally, an updatable head would require the UPDATE
-- capability `roles.sql` withholds and `probe()` disproves — the schema would demand a
-- power the design forbids. Evidentially, the history is the witness: every row here is the
-- platform saying "stream X had N entries at time T", signed by the head hash. A local head
-- later found BELOW a shipped observation is truncation proven by the platform's own prior
-- statement, with no inference about shipping lag required.
--
-- That is what makes FR-013's tail case decidable. Entries above the last shipped
-- observation are pending; entries below it that have gone missing are gone.
CREATE TABLE IF NOT EXISTS shipped_head_observations (
    correlation_id TEXT        NOT NULL,
    highest_seq    INTEGER     NOT NULL,
    head_hash      TEXT        NOT NULL,
    observed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Same first-write-wins reasoning. A rewrite that keeps the stream length constant
    -- collides here on the honest hash and changes nothing.
    PRIMARY KEY (correlation_id, highest_seq)
);

CREATE INDEX IF NOT EXISTS shipped_heads_by_stream
    ON shipped_head_observations (correlation_id, highest_seq DESC);
