-- SPDX-License-Identifier: Apache-2.0
-- Evidence schema (specs/008-northbound-api/data-model.md).
--
-- Separate from the durability schema because it is owned by a different subsystem and
-- granted to a different role. Nothing here is ever updated or deleted: the evidence role
-- holds SELECT on audit_entries and no grant at all on audit_stream_heads, so append-only
-- is enforced by the grant rather than by everyone remembering.

CREATE TABLE IF NOT EXISTS audit_entries (
    -- The bounding dimension of every read, present ON the row being filtered rather than
    -- joined: a join would make the boundary depend on another table being correct.
    tenant_id      TEXT        NOT NULL,
    correlation_id TEXT        NOT NULL,
    seq            INTEGER     NOT NULL,
    event_type     TEXT        NOT NULL,
    timestamp      TIMESTAMPTZ NOT NULL,
    payload        JSONB       NOT NULL,
    prev_hash      TEXT        NOT NULL,
    entry_hash     TEXT        NOT NULL,
    -- Also the concurrency backstop: two writers racing for the same position collide
    -- here rather than corrupting the chain.
    PRIMARY KEY (correlation_id, seq)
);

-- Every query is tenant-bounded first, so the index leads with it.
CREATE INDEX IF NOT EXISTS audit_by_tenant_time
    ON audit_entries (tenant_id, timestamp);

-- The highest position written to each chain.
--
-- Exists because a hash chain cannot detect truncation. It proves no record was modified
-- and none removed from the middle -- both break the seq sequence or the prev_hash link --
-- but delete the newest three and seq 0..N-4 verifies perfectly. Deleting the latest
-- entries is the obvious move against a log of who read what.
--
-- The evidence role holds NO grant here, not even SELECT, so the read path cannot even
-- learn what it would need to forge.
CREATE TABLE IF NOT EXISTS audit_stream_heads (
    correlation_id TEXT PRIMARY KEY,
    highest_seq    INTEGER     NOT NULL,
    head_hash      TEXT        NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
