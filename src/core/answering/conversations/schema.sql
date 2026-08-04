-- SPDX-License-Identifier: Apache-2.0
-- Ask conversations: what a person asked, grouped so they can come back to it (035).
--
-- SEPARATE FROM `threads` ON PURPOSE, and the separation is the feature's load-bearing
-- structure rather than an organizational preference. ADR-0039 divides asking from acting: a
-- thread is where turns ACT, an ask never does. Storing both in one table with a type column
-- would put "an ask cannot start a run" one refactor away from false. These tables have no
-- run_id, no agent_definition_id, and no path to dispatch — the property is enforced by
-- there being nothing here to enforce it against.
--
-- Deletable by their owner for the same reason threads are: this is a READING of asks the
-- trail already records. Deleting a reading removes no record. `audit_entries` is untouched
-- by everything in this file, and nothing here references it.

-- A conversation's spine. Created by its first ask, never empty.
CREATE TABLE IF NOT EXISTS ask_conversations (
    conversation_id TEXT PRIMARY KEY,
    tenant_id       TEXT        NOT NULL,
    subject_user_id TEXT        NOT NULL,
    -- Derived from the first question, once. There is no rename operation (035 defers it),
    -- so this cannot drift from what was actually asked.
    title           TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL,
    -- Bumped on every append. The list sorts by it, so the conversation somebody just used
    -- is the one at the top.
    last_asked_at   TIMESTAMPTZ NOT NULL
);

-- Listing, keyset-friendly, newest activity first.
CREATE INDEX IF NOT EXISTS ask_conversations_by_subject
    ON ask_conversations (tenant_id, subject_user_id, last_asked_at DESC, conversation_id DESC);

-- One exchange: a question and what came back.
--
-- Insert-only; rows die only with their conversation. `outcome` holds the response body the
-- surface returned VERBATIM, so reopening a conversation re-renders what the person actually
-- saw rather than re-deriving it from a corpus that may since have been re-pinned.
CREATE TABLE IF NOT EXISTS ask_exchanges (
    conversation_id TEXT        NOT NULL
        REFERENCES ask_conversations (conversation_id) ON DELETE CASCADE,
    -- Dense per-conversation ordering, assigned under the conversation's row lock. Two tabs
    -- asking at once cannot interleave into ambiguity — the same discipline `thread_turns`
    -- uses, for the same reason.
    seq             INTEGER     NOT NULL,
    question        TEXT        NOT NULL,
    -- What the ask actually consulted. This is the value a signal-less follow-up INHERITS,
    -- so it is stored rather than recomputed: re-deriving it later would make routing depend
    -- on a vocabulary that has since changed.
    source          TEXT        NOT NULL,
    disposition     TEXT        NOT NULL,
    outcome         JSONB       NOT NULL,
    asked_at        TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (conversation_id, seq)
);

-- Reading a conversation: its exchanges in order. Also serves context assembly, which wants
-- the most recent few.
CREATE INDEX IF NOT EXISTS ask_exchanges_by_conversation
    ON ask_exchanges (conversation_id, seq DESC);
