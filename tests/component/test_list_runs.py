# SPDX-License-Identifier: Apache-2.0
"""Listing runs through the operation, over the in-memory index.

The index's own rules have rows in `test_run_index.py`. What this file adds is what the
*operation* does with them: joining state from the durable record, refusing rather than
returning an empty list when the index cannot be read, and disclosing nothing about what
was withheld.

**The empty-versus-unreadable distinction is the one worth guarding.** An empty list means
"you have started nothing" and is a legitimate answer; a failed read is the platform not
knowing. Telling a person they have started nothing when the truth is that we could not
look is the only answer here that actively misleads.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.audit.sink import InMemoryAuditSink
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.run import RunState
from core.runs.index import InMemoryRunIndex, RunIndexEntry, RunIndexError
from surfaces.api.runs import list_runs_for

BASE = datetime(2026, 7, 28, 12, 0, tzinfo=UTC)


def _subject(user: str = "alice", tenant: str = "tenant-a") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id=user,
        tenant_id=tenant,
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


def _index(count: int, *, subject: str = "alice", tenant: str = "tenant-a") -> InMemoryRunIndex:
    index = InMemoryRunIndex()
    for n in range(1, count + 1):
        index.record(
            RunIndexEntry(
                run_id=f"run-{n:03d}",
                correlation_id=f"corr-{n:03d}",
                subject_user_id=subject,
                tenant_id=tenant,
                agent_definition_id="planner-agent",
                created_at=BASE + timedelta(minutes=n),
            )
        )
    return index


class Durability:
    """Returns a terminal state for runs it knows, and nothing for the rest."""

    def __init__(self, states: dict[str, str] | None = None, *, raises: bool = False) -> None:
        self._states = states or {}
        self._raises = raises

    def load(self, blob_id: str) -> Any:
        if self._raises:
            raise RuntimeError("durability unreachable")
        state = self._states.get(blob_id)
        if state is None:
            return None

        class _Blob:
            outcome = type("O", (), {"state": state, "stop_reason": None})()

        return _Blob()


def test_a_subject_lists_their_own_runs() -> None:
    page = list_runs_for(subject=_subject(), index=_index(3), audit=InMemoryAuditSink())

    assert [r.run_id for r in page.runs] == ["run-003", "run-002", "run-001"]


def test_the_state_is_joined_from_the_durable_record() -> None:
    """The index never carries state; a listing joins it at read time."""
    page = list_runs_for(
        subject=_subject(),
        index=_index(2),
        durability=Durability({"run-002": "completed"}),
        audit=InMemoryAuditSink(),
    )

    by_id = {r.run_id: r.state for r in page.runs}
    assert by_id["run-002"] is RunState.COMPLETED
    assert by_id["run-001"] is None  # still running: no terminal outcome yet


def test_an_unreadable_state_still_lists_the_run() -> None:
    """A person asking what they started should learn it exists.

    Guessing a state would be worse than admitting the gap; omitting the run would be
    worse still, because the run is exactly what they asked about.
    """
    page = list_runs_for(
        subject=_subject(),
        index=_index(1),
        durability=Durability(raises=True),
        audit=InMemoryAuditSink(),
    )

    assert [r.run_id for r in page.runs] == ["run-001"]
    assert page.runs[0].state is None


def test_an_unreadable_index_refuses_rather_than_returning_empty() -> None:
    """The distinction this file exists for."""

    class Broken:
        def list_for(self, **_: Any) -> Any:
            raise RunIndexError("index unreachable")

    with pytest.raises(RunIndexError):
        list_runs_for(subject=_subject(), index=Broken(), audit=InMemoryAuditSink())


def test_the_response_carries_no_total() -> None:
    """FR-004 at the response shape, not only at the cursor.

    A `total` field would be the withholding disclosure arrived at through helpfulness —
    and it is the field every list API grows eventually unless something forbids it.
    """
    page = list_runs_for(subject=_subject(), index=_index(9), limit=2, audit=InMemoryAuditSink())

    assert not any(
        field in page.model_dump() for field in ("total", "count", "total_count", "pages")
    ), "the list response grew a count of what the caller cannot see"
    assert page.cursor is not None


def test_paging_reaches_every_run_exactly_once() -> None:
    """The property a person actually depends on, asserted end to end rather than per page."""
    index = _index(7)
    seen: list[str] = []
    cursor: str | None = None

    while True:
        page = list_runs_for(
            subject=_subject(), index=index, limit=3, cursor=cursor, audit=InMemoryAuditSink()
        )
        seen.extend(r.run_id for r in page.runs)
        cursor = page.cursor
        if cursor is None:
            break

    assert seen == sorted(seen, reverse=True)
    assert len(seen) == len(set(seen)) == 7
