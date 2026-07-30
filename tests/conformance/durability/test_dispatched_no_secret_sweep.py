# SPDX-License-Identifier: Apache-2.0
"""No credential material in the state store — extended to `grants` (014 T017, SC-003).

005's sweep asserted this about a checkpoint BLOB, in process. This asserts it about the live
tables, which is the stronger claim and the one FR-012 makes: not "the object we just built
carries no secret" but "nothing in the store does".

**The extension to `grants` is the point.** 014 added a table holding consent — subject,
definition, scope, expiry — and a table that did not exist cannot have been swept. FR-012
extends to it by ROW, not by remark: `DelegationGrant` has no field for credential material,
so this cannot fail today, which is exactly when to write it down. The next person who wants
"just the credential id, for correlation" on that record has to delete an assertion whose
message says why not — and the reason is that `checkpoints.grant_id` already held a credential
id once (research F1).
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.conformance.durability import dispatch_harness as h

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

#: Matched against every stored value. The same list 005's blob-level sweep uses, so the two
#: cannot drift into disagreeing about what a secret looks like.
FORBIDDEN = ("credential", "token", "secret", "password", "run_salt", "hvs.", "private_key")


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


def _sweep(conn: Any, table: str, columns: str) -> None:
    rows = h.query(conn, f"SELECT {columns} FROM {table}")  # noqa: S608 — literal, not caller input
    assert rows, (
        f"{table} is empty, so this sweep asserted nothing. Run the dispatch rows first — a "
        f"no-secret sweep over no rows is the vacuous pass this suite exists to avoid."
    )
    for row in rows:
        rendered = " ".join(str(value).lower() for value in row)
        for needle in FORBIDDEN:
            assert needle not in rendered, (
                f"{table} contains {needle!r}: {row!r}. The state store holds state, never "
                f"authority (Principle IV, FR-012)"
            )


def test_row_the_grants_table_holds_consent_metadata_and_nothing_else(conn: Any) -> None:
    """The new table, swept against the live store.

    Every column, not a chosen subset: a sweep that named the columns it trusted would pass
    over the one somebody added.
    """
    _sweep(
        conn,
        "grants",
        "grant_id, subject_user_id, agent_definition_id, requested_scope, issued_at, expires_at",
    )


def test_row_checkpoints_still_hold_no_credential_material(conn: Any) -> None:
    """005's property, re-asserted against the live table rather than a blob.

    Load-bearing for 014 specifically: the feature CHANGED what goes in `grant_id`. It used to
    receive `run.authority.credential_id` — a task credential's identifier in the column
    ADR-0026 defined as referencing durable consent. That is the kind of write this sweep
    exists to catch, and it went uncaught for nine features because the sweep ran over an
    in-process object rather than the store.
    """
    _sweep(
        conn,
        "checkpoints",
        "blob_id, payload, correlation_id, grant_id, written_by, run_state, stop_reason",
    )


def test_row_a_checkpoint_written_since_the_grant_store_existed_resolves(conn: Any) -> None:
    """The other half of F1: the reference resolves, on real rows.

    For nine features `checkpoints.grant_id` pointed at nothing — a column ADR-0026 described
    as referencing durable consent, holding the 15-minute task credential's id instead. A
    resume loading consent by that value finds nothing and refuses every revival, so this is
    not tidiness: it is whether US4 is evaluable at all.

    **Scoped to checkpoints written since the store existed, and that bound is the honest
    part.** The first version of this row asserted the property over every checkpoint in the
    database and failed on 51 rows — every `api-conformance-run-*`, `identity-e2e-*`,
    `divergence-*`, and `pack-dispatch-*` checkpoint written before 014. Those rows are F1's
    footprint: real evidence of the defect, and unfixable by any code change, because the
    credential ids they hold never named anything that was stored. A gate that demanded the
    past be correct would be permanently red for a reason nobody could act on.

    So the claim is the one that can be true: from the moment consent became durable, every
    checkpoint referencing it resolves. The pre-store rows are counted rather than ignored —
    a shrinking-to-zero number would mean someone quietly deleted the evidence.
    """
    epoch = h.query(conn, "SELECT min(issued_at) FROM grants")[0][0]
    assert epoch is not None, (
        "no grants exist at all, so this row asserted nothing — run the dispatch rows first"
    )

    dangling = h.query(
        conn,
        "SELECT c.blob_id, c.grant_id FROM checkpoints c "
        "LEFT JOIN grants g ON g.grant_id = c.grant_id "
        "WHERE c.grant_id <> '' AND g.grant_id IS NULL AND c.written_at >= %s",
        (epoch,),
    )
    assert dangling == [], (
        f"checkpoints written since the grant store existed reference grants that do not: "
        f"{dangling}. A resume loading consent by these ids refuses `grant_missing` — the "
        f"correct refusal for an incorrect write (research F1)"
    )

    legacy = h.query(
        conn,
        "SELECT count(*) FROM checkpoints c LEFT JOIN grants g ON g.grant_id = c.grant_id "
        "WHERE c.grant_id <> '' AND g.grant_id IS NULL AND c.written_at < %s",
        (epoch,),
    )[0][0]
    print(f"pre-014 checkpoints holding an unresolvable grant_id: {legacy} (F1's footprint)")
