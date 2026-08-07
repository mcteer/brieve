-- SPDX-License-Identifier: Apache-2.0
-- Endorsed customer content: the words, versioned and immutable (045, T005).
--
-- **Why this is not in the repository tree.** `corpus-sync` writes into `corpus/` — vendored,
-- reviewed, shipped, identical in every deployment (Principle VII). Customer content arrives at
-- runtime in one deployment; there is no commit to put it in, and an allocation's filesystem
-- does not survive rescheduling. So it lives in the store the platform already operates
-- (Principle VI: nothing new to run). Governance in the fabric, weight here — the split the
-- audit plane already uses.
--
-- **A version is written once and never updated.** Adoption does not rewrite content; it points
-- the governance record at a different version_id. That is what lets a run in flight keep
-- reading the ground it started on while an administrator adopts a newer one (US4) — the two
-- are not competing for the same rows.
--
-- **Superseded versions are retained, and the deferral is recorded rather than silent** (R3).
-- A version is unreferencable only when no run record cites it and no suspended run pins it,
-- so deletion is a decision with a query behind it, not a TTL. 040's kept-requests shape.
--
-- Every statement is IF NOT EXISTS, so `migrate()` stays safe to re-apply on every boot.

-- One sync of one source. `version_id` is the content identity a run pins and a record names.
CREATE TABLE IF NOT EXISTS endorsed_versions (
    version_id     TEXT PRIMARY KEY,
    tenant_id      TEXT        NOT NULL,
    source         TEXT        NOT NULL,
    -- What the source said it was at sync time. Detection compares against this WITHOUT
    -- transferring content — a refs listing, which is why noticing drift is cheap enough to
    -- ride the health checker rather than needing a schedule of its own (R5).
    upstream_tip   TEXT        NOT NULL,
    synced_at      TIMESTAMPTZ NOT NULL,
    -- The administrator whose act triggered the sync. A version with no author would be
    -- content that appeared, and FR-002's whole point is that somebody is answerable for it.
    synced_by      TEXT        NOT NULL,
    -- candidate | adopted | superseded. A review-sync lands as `candidate` and changes
    -- nothing about answers until an adoption flips it (detect != adopt, FR-017a).
    state          TEXT        NOT NULL,
    document_count INTEGER     NOT NULL
);

-- Finding a source's versions, newest first: the review page and the drift probe both want it.
CREATE INDEX IF NOT EXISTS endorsed_versions_by_source
    ON endorsed_versions (tenant_id, source, synced_at DESC);

-- The documents of one version. Insert-only, like its parent.
--
-- `digest` is over `body`, and it is verified on read. That is the endorsed half of what
-- `load_corpus(verify=True)` does for the pinned corpus, and it must exist here for the same
-- reason: a citation resolving against a pin whose content has changed underneath is a
-- citation to something other than what was endorsed.
CREATE TABLE IF NOT EXISTS endorsed_documents (
    version_id TEXT NOT NULL
        REFERENCES endorsed_versions (version_id) ON DELETE CASCADE,
    -- The full citation path, `/endorsed/<source>/<relative>`. Stored rendered rather than
    -- assembled at read time so that what resolution matches on is what was written down.
    path       TEXT NOT NULL,
    url        TEXT NOT NULL,
    digest     TEXT NOT NULL,
    PRIMARY KEY (version_id, path)
);

-- One citable section. The anchor set of a document is the rows here, so an anchor that has
-- no text cannot exist — which is precisely the "resolves to nothing" state the citation gate
-- refuses, made unrepresentable rather than checked.
CREATE TABLE IF NOT EXISTS endorsed_sections (
    version_id TEXT NOT NULL,
    path       TEXT NOT NULL,
    anchor     TEXT NOT NULL,
    body       TEXT NOT NULL,
    PRIMARY KEY (version_id, path, anchor),
    FOREIGN KEY (version_id, path)
        REFERENCES endorsed_documents (version_id, path) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS endorsed_sections_by_version
    ON endorsed_sections (version_id, path);
