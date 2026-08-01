# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation, GATE:fail-closed, GATE:no-secret-leak — a read leaves a record.

**Every row here would have failed on 2026-08-01**, when nine of seventeen operations returned
records about runs and threads and wrote nothing, while both surfaces told every connecting
client that every operation is recorded in a tamper-evident trail.

The defect was found by connecting an editor to the running service and asking the platform what
it had just done. The answer came back; the question left no trace. Nothing in the 857-test suite
compared what the platform *says* to what it *does* — including
`test_operations_audited.py`, whose name promises exactly that and whose rows assert
unauthenticated refusal instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.audit.schema import AuditEntry, AuditEventType
from core.audit.sink import AuditSink, InMemoryAuditSink
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.runs.index import InMemoryRunIndex, RunIndexEntry
from core.runs.refusals import OperationRefused
from surfaces.api.record_access import (
    RecordAccessUnavailable,
    record_stream_for,
)
from surfaces.api.runs import RESULT_KEY, list_runs_for, run_result_for, stop_run_for

TENANT = "tenant-a"

#: A value shaped like something that must never reach the trail. Planted, not reasoned about.
PLANTED_SECRET = "hvs.CAESIJx-notarealtoken-butshapedlikeone"


def _subject(user: str = "alice", tenant: str = TENANT) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id=user,
        tenant_id=tenant,
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


def _index(*, subject: str = "alice", tenant: str = TENANT) -> InMemoryRunIndex:
    index = InMemoryRunIndex()
    index.record(
        RunIndexEntry(
            run_id="run-1",
            correlation_id="corr-1",
            subject_user_id=subject,
            tenant_id=tenant,
            agent_definition_id="planner-agent",
            created_at=datetime(2026, 7, 28, tzinfo=UTC),
        )
    )
    return index


class _Durability:
    def __init__(self, payload: dict[str, Any] | None = None, state: str = "completed") -> None:
        self._payload = payload
        self._state = state
        self.saved: list[Any] = []

    def load(self, blob_id: str) -> Any:
        if self._payload is None:
            return None

        class _Outcome:
            state = self._state
            stop_reason = None

        class _Blob:
            payload = self._payload
            outcome = _Outcome()
            correlation_id = "corr-1"
            grant_id = ""
            step_index = 0

        return _Blob()

    def save(self, blob: Any) -> None:
        self.saved.append(blob)


class _FailingSink(InMemoryAuditSink):
    """A sink that refuses the record-access write and nothing else.

    Narrow on purpose: a sink failing every write would also break the run's own entries, and
    the row would then pass for the wrong reason.
    """

    def __init__(self, *, fail_on: set[AuditEventType] | None = None) -> None:
        super().__init__()
        self._fail_on = fail_on or {
            AuditEventType.RECORD_READ,
            AuditEventType.RECORD_READ_REFUSED,
            AuditEventType.RUN_STOPPED,
            AuditEventType.THREAD_CREATED,
        }

    def append_event(self, **kwargs: Any) -> AuditEntry:
        if kwargs.get("event_type") in self._fail_on:
            raise RuntimeError("the trail is unwritable")
        return super().append_event(**kwargs)


def _reads(sink: AuditSink, tenant: str = TENANT) -> list[AuditEntry]:
    return list(sink.list_by_correlation_id(record_stream_for(tenant)))


# ---------------------------------------------------------------- a read leaves a record


def test_reading_a_runs_result_records_who_read_it() -> None:
    """FR-003, and the sharpest case in the feature.

    021 kept the run's result out of `RunReport` so a tenant-scoped report could not route
    around this operation's subject-only restriction. The reasoning was sound and the code held
    it — and this operation, the one that actually serves the result, recorded nothing about who
    read it. The artifact that could not leak it was audited; the one that served it was not.
    """
    sink = InMemoryAuditSink()
    run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=_Durability({RESULT_KEY: {"ok": True}}),
        audit=sink,
    )

    entries = _reads(sink)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.event_type is AuditEventType.RECORD_READ
    assert entry.payload["subject_user_id"] == "alice"
    assert entry.payload["operation"] == "get_run_result"
    # FR-005: holding the run's correlation id is enough to find who read it.
    assert entry.payload["target_correlation_id"] == "corr-1"
    assert entry.payload["target_id"] == "run-1"


def test_a_listing_records_and_carries_no_single_target() -> None:
    """FR-005 — null rather than absent, so the field's meaning does not depend on presence."""
    sink = InMemoryAuditSink()
    list_runs_for(subject=_subject(), index=_index(), audit=sink)

    entry = _reads(sink)[0]
    assert entry.payload["operation"] == "list_runs"
    assert entry.payload["target_correlation_id"] is None
    assert entry.payload["result_count"] == 1


def test_an_empty_listing_still_records() -> None:
    """FR-007b. An empty page discloses that the caller asked.

    A trail that omits fruitless reads cannot show probing, which is the pattern most worth
    seeing in it.
    """
    sink = InMemoryAuditSink()
    list_runs_for(subject=_subject(), index=InMemoryRunIndex(), audit=sink)

    entry = _reads(sink)[0]
    assert entry.payload["result_count"] == 0


def test_each_call_records_again() -> None:
    """US1 acceptance 3. A record of *has ever been read* is not a record of who read it."""
    sink = InMemoryAuditSink()
    for _ in range(3):
        list_runs_for(subject=_subject(), index=_index(), audit=sink)

    assert len(_reads(sink)) == 3


def test_stopping_a_run_records_who_stopped_it() -> None:
    """FR-002b, and the finding that analysis pass 8 made against the code.

    This feature's own spec asserted `stop_run` was already covered — in an assumption labelled
    *"Measured, not assumed"*. Only `start_run` had been measured. `stop_run_for` wrote a
    checkpoint blob carrying ``written_by="stop:{user}"`` and returned: no audit entry at all,
    and no ``STOP`` member in the vocabulary. A person deliberately withdrawing consent and
    ending a run left nothing hash-chained and nothing reachable through the governed path.

    **On the run's own stream, not the reader stream** — this is an act performed on the run
    rather than a read of it, so it belongs where `THREAD_DELETED` belongs.
    """
    sink = InMemoryAuditSink()
    stop_run_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=_Durability(),
        audit=sink,
    )

    assert _reads(sink) == [], "a stop is not a read and does not belong in the reader stream"
    stopped = [
        e
        for e in sink.list_by_correlation_id("corr-1")
        if e.event_type is AuditEventType.RUN_STOPPED
    ]
    assert len(stopped) == 1
    assert stopped[0].payload["subject_user_id"] == "alice"
    assert stopped[0].payload["stop_reason"] == "stopped_by:alice"


# ---------------------------------------------------------------- refusals


def test_a_refused_read_records_and_keeps_what_the_caller_cannot_see() -> None:
    """FR-007, SC-007.

    The caller gets one answer for both; the trail keeps two. A run of `outside_tenant` is
    someone probing, and a trail that had collapsed them would show a user who mistypes a lot.
    A boundary probeable without trace is what this prevents.
    """
    sink = InMemoryAuditSink()

    with pytest.raises(OperationRefused):
        run_result_for(
            run_id="run-1",
            subject=_subject(tenant="tenant-b"),
            index=_index(),
            durability=_Durability(),
            audit=sink,
        )
    with pytest.raises(OperationRefused):
        run_result_for(
            run_id="run-1",
            subject=_subject(user="mallory"),
            index=_index(),
            durability=_Durability(),
            audit=sink,
        )

    absent, theirs = _reads(sink, "tenant-b"), _reads(sink)
    assert absent[0].event_type is AuditEventType.RECORD_READ_REFUSED
    assert absent[0].payload["disposition"] == "no_such_record"
    assert theirs[0].payload["disposition"] == "not_permitted"


# ---------------------------------------------------------------- GATE:fail-closed


@pytest.mark.parametrize(
    ("call", "kwargs"),
    [
        (list_runs_for, {"index": _index()}),
        (run_result_for, {"run_id": "run-1", "index": _index(), "durability": _Durability()}),
    ],
)
def test_a_read_that_cannot_be_recorded_returns_nothing(call: Any, kwargs: Any) -> None:
    """FR-007a, SC-009. **Listings included, and that is the case with no precedent.**

    An access that succeeded while its record did not is the state this whole feature exists to
    end, so serving one during a trail outage would reintroduce it at exactly the moment
    someone will later investigate. The accepted cost is stated in the spec rather than
    discovered here: a trail outage makes runs and threads unreadable on both surfaces.
    """
    with pytest.raises(RecordAccessUnavailable):
        call(subject=_subject(), audit=_FailingSink(), **kwargs)


def test_a_stop_that_cannot_be_recorded_leaves_the_run_running() -> None:
    """FR-007a for the one write among the seven.

    Strictly worse than a refused read: a run silently terminated with no record is a caller
    who believes it worked. So the entry goes first, and the terminal save never happens.
    """
    durability = _Durability()
    with pytest.raises(RecordAccessUnavailable):
        stop_run_for(
            run_id="run-1",
            subject=_subject(),
            index=_index(),
            durability=durability,
            audit=_FailingSink(),
        )
    assert durability.saved == [], "the run was terminated with no record of who did it"


# ---------------------------------------------------------------- GATE:no-secret-leak


def test_no_record_carries_the_content_it_described() -> None:
    """FR-006, SC-006. Planted, not reasoned about.

    Recording that a payload was read must not copy the payload into the trail: the trail does
    not egress by default, and a payload inside it inherits neither that boundary's intent nor
    this operation's subject restriction.
    """
    sink = InMemoryAuditSink()
    run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=_Durability({RESULT_KEY: {"token": PLANTED_SECRET}}),
        audit=sink,
    )

    for entry in _reads(sink):
        assert PLANTED_SECRET not in entry.model_dump_json()


# ---------------------------------------------------------------- GATE:correlation


def test_reading_a_run_leaves_that_runs_chain_untouched() -> None:
    """FR-005a, SC-010. **The row that protects 021.**

    An early draft of this spec required a read to join the read object's own walk. The evidence
    path had already refused that shape — appending to the chain being read means reading
    evidence writes into the evidence being read — and `RunReport` makes it worse, since it
    compiles from a run's chain: a read appended there would put "who read this run" inside the
    report of that run, including reads of the report, growing every time anyone looked.

    This row is the guard against that reasoning coming back.
    """
    sink = InMemoryAuditSink()
    sink.append_event(
        correlation_id="corr-1",
        tenant_id=TENANT,
        event_type=AuditEventType.RUN_START,
        payload={},
    )
    before = [e.entry_hash for e in sink.list_by_correlation_id("corr-1")]

    run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=_Durability({RESULT_KEY: {"ok": True}}),
        audit=sink,
    )

    after = [e.entry_hash for e in sink.list_by_correlation_id("corr-1")]
    assert after == before, "reading a run altered the chain a report of that run compiles from"


def test_the_reader_stream_is_reachable_through_the_governed_path() -> None:
    """FR-005b, added by analysis pass 1 — *a record nobody can query is not a record*.

    Nothing else covered this. The one artifact that should have exposed the gap was the served
    demonstration, and it was querying Postgres directly and skipping the governed path
    entirely, so the two concealed each other.
    """
    from core.audit.query import EvidenceQueryRequest
    from tests.harness.memory_evidence import InMemoryEvidenceQuery

    sink = InMemoryAuditSink()
    list_runs_for(subject=_subject(), index=_index(), audit=sink)
    query = InMemoryEvidenceQuery(sink)

    found = query.search(
        EvidenceQueryRequest(tenant_id=TENANT, correlation_id=record_stream_for(TENANT), limit=10)
    )
    assert [e.event_type for e in found] == [AuditEventType.RECORD_READ]

    # ...and bounded by tenant like any other evidence: the reader stream is not a side channel
    # around the boundary every other read is subject to.
    assert (
        query.search(
            EvidenceQueryRequest(
                tenant_id="tenant-b", correlation_id=record_stream_for(TENANT), limit=10
            )
        )
        == []
    )


# ---------------------------------------------------------------- FR-015


def test_recording_changed_no_operations_answer() -> None:
    """SC-004a, FR-015. A negative requirement with no check is a hope.

    Seven operations were edited. This asserts the edit added a record and changed nothing about
    who may call them or what they return — a narrower claim than "authorized correctly", and
    the distinction is the point.
    """
    sink = InMemoryAuditSink()
    page = list_runs_for(subject=_subject(), index=_index(), audit=sink)
    assert [r.run_id for r in page.runs] == ["run-1"]

    result = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=_Durability({RESULT_KEY: {"ok": True}}),
        audit=sink,
    )
    assert result.disposition == "complete"
    assert result.result == {"ok": True}

    # Still refused, for the same reasons, to the same callers.
    for subject, code in (
        (_subject(user="mallory"), "not_permitted"),
        (_subject(tenant="x"), "no_such_record"),
    ):
        with pytest.raises(OperationRefused) as refusal:
            run_result_for(
                run_id="run-1",
                subject=subject,
                index=_index(),
                durability=_Durability(),
                audit=sink,
            )
        assert refusal.value.reason_code == code


# ---------------------------------------------------------------- the record is honest


def test_a_too_large_result_records_a_size_refusal_not_a_permission_denial() -> None:
    """FR-007c, found by analysis pass 10 reading the code rather than the artifacts.

    This refusal raised `not_permitted` — *"the record is visible to this caller, and this
    action is not theirs"* — for a result that merely did not fit. A misleading 403 on its own;
    once 022 began recording refusals it would have written a permission denial into the trail
    for something that was never about permission. The vocabulary had already settled the
    question twice: `message_too_large` exists for this shape, and `nothing_to_dispatch` carries
    the comment about exactly this conflation.
    """
    from surfaces.api.runs import MAX_RESULT_BYTES

    sink = InMemoryAuditSink()
    with pytest.raises(OperationRefused) as refusal:
        run_result_for(
            run_id="run-1",
            subject=_subject(),
            index=_index(),
            durability=_Durability({RESULT_KEY: "x" * (MAX_RESULT_BYTES + 1)}),
            audit=sink,
        )
    assert refusal.value.reason_code == "result_too_large"

    entry = _reads(sink)[0]
    assert entry.event_type is AuditEventType.RECORD_READ_REFUSED
    assert entry.payload["disposition"] == "result_too_large"


def test_a_record_never_overstates_what_was_shown() -> None:
    """A read of a run still working discloses nothing, and the entry must say so.

    An entry reading *"read, one result"* when the answer was `running` describes a disclosure
    that did not happen. A record that overstates what someone saw is the same class of defect
    as no record at all — it just fails in the other direction.
    """
    sink = InMemoryAuditSink()
    response = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=_Durability(),
        audit=sink,
    )
    assert response.disposition == "running"
    assert _reads(sink)[0].payload["result_count"] == 0
