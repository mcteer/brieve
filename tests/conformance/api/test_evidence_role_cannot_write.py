# SPDX-License-Identifier: Apache-2.0
"""Row: the read path cannot mutate — enforced by Postgres, not by application code.

This is **defence #2** (FR-009, SC-007). Defence #1 is that ``EvidenceQuery`` names no
write method, which holds only while application code is correct and is the one a future
refactor removes by handing the read path a writable connection.

So this row deliberately does the thing that refactor would do: it takes a raw connection
under the evidence role and attempts to write through it directly, bypassing every Python
guard. If the grant is right, Postgres refuses. A test that only asserted the Protocol has
no ``append`` would pass against a completely open database.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.enclave


def _refused(conn: Any, sql: str) -> bool:
    """True when Postgres refuses the statement."""
    cur = conn.cursor()
    try:
        cur.execute(sql)
        conn.commit()
        return False
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return True


def test_insert_is_refused(evidence_connection: Any) -> None:
    # TEMPORARY (T012): deliberately broken to prove the lane goes red. Reverted next commit.
    assert False, "T012: deliberate failure to prove the enclave lane fails on a broken row"
    assert _refused(
        evidence_connection,
        "INSERT INTO audit_entries "
        "(tenant_id, correlation_id, seq, event_type, timestamp, payload, prev_hash, entry_hash) "
        "VALUES ('t', 'forged', 0, 'run_start', now(), '{}', 'x', 'y')",
    )


def test_update_is_refused(evidence_connection: Any) -> None:
    assert _refused(evidence_connection, "UPDATE audit_entries SET payload = '{}'")


def test_delete_is_refused(evidence_connection: Any) -> None:
    assert _refused(evidence_connection, "DELETE FROM audit_entries")


def test_stream_heads_are_unreachable(evidence_connection: Any) -> None:
    """Not even readable.

    The heads are what make truncation detectable. A read path able to see them could
    learn exactly what it would need to forge to make a truncated chain look intact.
    """
    assert _refused(evidence_connection, "SELECT * FROM audit_stream_heads")


def test_the_role_can_still_do_its_job(evidence_connection: Any) -> None:
    """The narrowing must not have gone so far that the read path cannot read.

    Without this, every assertion above would also pass against a role granted nothing at
    all, which would be a broken feature reported as a healthy one.
    """
    cur = evidence_connection.cursor()
    cur.execute("SELECT count(*) FROM audit_entries")
    assert cur.fetchone() is not None
