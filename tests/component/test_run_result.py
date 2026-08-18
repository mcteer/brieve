# SPDX-License-Identifier: Apache-2.0
"""Retrieving what a run produced — three dispositions an empty answer would conflate.

Today the only path to a run's output is reading its evidence and reassembling it. That is
a *forensic* path: it exists so an investigator can determine what happened, and using it
as the product path puts the burden of interpretation on every client, guarantees each one
interprets differently, and makes the audit trail's shape a compatibility surface.

The three dispositions are the point. A single empty response would say the same thing
about a run still working, a run that finished having produced nothing, and a run that was
stopped — and only one of those is a reason to wait.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.audit.sink import InMemoryAuditSink
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.runs.index import InMemoryRunIndex, RunIndexEntry
from core.runs.refusals import OperationRefused
from surfaces.api.runs import MAX_RESULT_BYTES, RESULT_KEY, run_result_for


def _subject(user: str = "alice", tenant: str = "tenant-a") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id=user,
        tenant_id=tenant,
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


def _index(*, subject: str = "alice", tenant: str = "tenant-a") -> InMemoryRunIndex:
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


class Durability:
    def __init__(self, blob: Any = None) -> None:
        self._blob = blob

    def load(self, blob_id: str) -> Any:
        return self._blob


def _blob(
    *, state: str | None, payload: dict[str, Any] | None = None, stop_reason: str | None = None
) -> Any:
    class _Outcome:
        pass

    outcome = None
    if state is not None:
        outcome = _Outcome()
        outcome.state = state  # type: ignore[attr-defined]
        outcome.stop_reason = stop_reason  # type: ignore[attr-defined]

    class _Blob:
        pass

    blob = _Blob()
    blob.outcome = outcome  # type: ignore[attr-defined]
    blob.payload = payload or {}  # type: ignore[attr-defined]
    return blob


def test_a_finished_run_returns_its_result() -> None:
    """The positive control, and the operation's whole purpose."""
    response = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=Durability(_blob(state="completed", payload={RESULT_KEY: {"plan": "ok"}})),
        audit=InMemoryAuditSink(),
    )

    assert response.disposition == "complete"
    assert response.result == {"plan": "ok"}


def test_a_running_run_says_so_rather_than_returning_nothing() -> None:
    """Distinguishable from a run that finished empty — one is worth waiting for."""
    response = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=Durability(_blob(state=None)),
        audit=InMemoryAuditSink(),
    )

    assert response.disposition == "running"
    assert response.result is None


def test_a_published_pr_is_complete_even_when_outcome_was_left_unset() -> None:
    """The proposer wrote pr_url onto RESULT_KEY and returned; Nomad then completed.

    get_run_result treated outcome=None as still running and hid the URL. The portal
    saw a terminal Nomad state with no result and said the Build ended without a PR.
    """
    response = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=Durability(
            _blob(
                state=None,
                payload={RESULT_KEY: {"pr_url": "https://github.com/example/repo/pull/1"}},
            )
        ),
        audit=InMemoryAuditSink(),
    )

    assert response.disposition == "complete"
    assert response.result == {"pr_url": "https://github.com/example/repo/pull/1"}


def test_a_running_build_returns_live_phase_progress() -> None:
    """The portal strip polls this while outcome is still None — progress must not wait."""
    progress = {
        "current": "research",
        "phases": [
            {"name": "research", "status": "active"},
            {"name": "plan", "status": "pending"},
        ],
    }
    response = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=Durability(_blob(state=None, payload={"propose_progress": progress})),
        audit=InMemoryAuditSink(),
    )

    assert response.disposition == "running"
    assert response.propose_progress == progress


def test_a_stopped_run_returns_its_reason_not_an_empty_result() -> None:
    """A run that failed is not a run that returned nothing.

    The reason is what makes the answer actionable, and an empty response would say the
    second thing about the first.
    """
    response = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=Durability(_blob(state="stopped", stop_reason="stopped_by:alice")),
        audit=InMemoryAuditSink(),
    )

    assert response.disposition == "ended_without_result"
    assert response.stop_reason == "stopped_by:alice"


def test_another_tenant_is_answered_as_absent() -> None:
    with pytest.raises(OperationRefused) as caught:
        run_result_for(
            run_id="run-1",
            subject=_subject(tenant="tenant-a"),
            index=_index(tenant="tenant-b"),
            durability=Durability(),
            audit=InMemoryAuditSink(),
        )

    assert caught.value.reason_code == "no_such_record"
    assert not caught.value.is_visible_to_caller


def test_someone_elses_run_in_the_same_tenant_is_refused_with_a_reason() -> None:
    with pytest.raises(OperationRefused) as caught:
        run_result_for(
            run_id="run-1",
            subject=_subject(user="alice"),
            index=_index(subject="bob"),
            durability=Durability(),
            audit=InMemoryAuditSink(),
        )

    assert caught.value.reason_code == "not_permitted"


def test_an_over_bound_result_refuses_rather_than_truncating() -> None:
    """A partial result presented as complete is worse than a refusal — someone acts on it.

    Measured on the serialised bytes, because that is what a caller receives: a structure
    small in objects and enormous in bytes is the case a length check would wave through.
    """
    enormous = {"rows": ["x" * 1024] * (MAX_RESULT_BYTES // 512)}

    with pytest.raises(OperationRefused) as caught:
        run_result_for(
            run_id="run-1",
            subject=_subject(),
            index=_index(),
            durability=Durability(_blob(state="completed", payload={RESULT_KEY: enormous})),
            audit=InMemoryAuditSink(),
        )

    assert "too large" in str(caught.value)


def test_break_fixture_the_raw_checkpoint_payload_is_never_returned() -> None:
    """The defect that passes every disposition row above.

    The result *is* in the payload, so returning the payload wholesale looks correct — and
    makes resume state a compatibility surface, which is the argument against
    reconstructing results from the audit trail, one layer down.
    """
    response = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=Durability(
            _blob(
                state="completed",
                payload={
                    RESULT_KEY: {"plan": "ok"},
                    "resume_step_index": 7,
                    "grant_id": "grant-internal",
                },
            )
        ),
        audit=InMemoryAuditSink(),
    )

    assert response.result == {"plan": "ok"}
    serialised = response.model_dump_json()
    assert "resume_step_index" not in serialised
    assert "grant_id" not in serialised, (
        "resume-internal state reached the caller, which makes the checkpoint's shape "
        "something clients depend on"
    )


def test_intake_message_is_the_stored_run_input() -> None:
    """048. The string comes from the store fixture, not a literal built inside the assertion.

    API and MCP expose this field by construction: they share ``RunResultResponse``. There is
    no second serializer.
    """
    from core.threads.records import RunInput
    from core.threads.store import InMemoryThreadStore

    store = InMemoryThreadStore()
    stored = RunInput(
        run_id="run-1",
        message="provision aws for the demo repo",
        created_at=datetime(2026, 8, 17, tzinfo=UTC),
    )
    store.put_run_input(stored)
    progress = {"current": "write", "phases": [{"name": "write", "status": "active"}]}
    response = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=Durability(_blob(state=None, payload={"propose_progress": progress})),
        audit=InMemoryAuditSink(),
        thread_store=store,
    )

    assert response.intake_message is stored.message
    assert response.propose_progress == progress


def test_missing_run_input_yields_null_intake_message() -> None:
    """Fail-closed miss: None, not an empty string, not a rail title."""
    from core.threads.store import InMemoryThreadStore

    response = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=Durability(_blob(state=None)),
        audit=InMemoryAuditSink(),
        thread_store=InMemoryThreadStore(),
    )

    assert response.intake_message is None
    assert response.intake_message != ""


def test_unreadable_store_still_returns_phase_progress() -> None:
    """Store errors do not invent a prompt and do not drop propose_progress."""

    class _Broken:
        def get_run_input(self, *, run_id: str) -> None:
            raise RuntimeError("store unreadable")

    progress = {"current": "plan", "phases": [{"name": "plan", "status": "active"}]}
    response = run_result_for(
        run_id="run-1",
        subject=_subject(),
        index=_index(),
        durability=Durability(_blob(state=None, payload={"propose_progress": progress})),
        audit=InMemoryAuditSink(),
        thread_store=_Broken(),
    )

    assert response.intake_message is None
    assert response.propose_progress == progress
