-- SPDX-License-Identifier: Apache-2.0
-- Eval schema (specs/013-capability-packs/data-model.md).
--
-- Applied at bring-up in infra/bin/enclave-up's existing statement block — the same pass,
-- the same SET ROLE brieve — because the rule there has now bitten four times and this is
-- the chance not to make it five. A results table left to migrate-on-first-use is owned by
-- whichever ephemeral credential happened to run first, and the next credential fails DDL
-- with "must be owner of table".
--
-- Results are RECORDS, not claims (Principle IX): a cell is qualified because a suite ran
-- and a result was written, and the result is retrievable. Written by core/evals; read on
-- the run path only through core/authority/matrix.py.

CREATE TABLE IF NOT EXISTS eval_results (
    -- The cell this result qualifies (or fails to). (pack, model, role) rather than a
    -- joined id, because the matrix record in Vault is keyed the same way and an
    -- investigator moves between the two.
    pack         TEXT        NOT NULL,
    model        TEXT        NOT NULL,
    role         TEXT        NOT NULL,
    suite        TEXT        NOT NULL,
    case_id      TEXT        NOT NULL,
    verdict      TEXT        NOT NULL,
    -- fixture | live. SC-013: a cell qualified against a recording must not read as more.
    scorer       TEXT        NOT NULL,
    -- Which judge scored it. Empty only for the seed-qualified first judge.
    judge        TEXT        NOT NULL DEFAULT '',
    scored_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (pack, model, role, suite, case_id, scored_at)
);

-- Read at review, never by a run: which results back which cell.
CREATE INDEX IF NOT EXISTS eval_results_by_cell
    ON eval_results (pack, model, role);
