# SPDX-License-Identifier: Apache-2.0
"""Collecting a change's disposition — the operation 008 reasoned for and did not ship.

008 chose 202 over 403 because *"a client that reads 403 stops asking, so a change approved
twenty minutes later is never collected"*. It then returned an accessor nothing stored, so
there was nothing to ask. These rows are that gap closed.

Hermetic: the store and the status source are both substitutable, so every branch —
including the ones a live fabric cannot be made to produce on demand — is reachable. The
end-to-end version against a real Control Group is a `host_enclave` row (T014).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.audit.sink import InMemoryAuditSink
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.runs.changes import (
    ChangeRequestRecord,
    CollectedDisposition,
    InMemoryChangeRequestStore,
)
from core.runs.refusals import OperationRefused
from surfaces.api.mappings import collect_mapping_change

ACCESSOR = "acc-abc123"


def _subject(user: str = "alice", tenant: str = "tenant-a") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id=user,
        tenant_id=tenant,
        subject_kind=SubjectKind.HUMAN,
        roles=frozenset({"operator"}),
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


class StatusSource:
    """Stands in for the trust fabric's status endpoint, counting how often it is asked."""

    def __init__(self, disposition: str = "pending", approvals: int = 0) -> None:
        self.disposition = disposition
        self.approvals = approvals
        self.calls = 0

    def status_of(self, accessor: str) -> CollectedDisposition:
        self.calls += 1
        return CollectedDisposition(
            accessor=accessor,
            disposition=self.disposition,
            approvals=self.approvals,
            required=2,
        )


def _store(*, requester: str = "alice", tenant: str = "tenant-a") -> InMemoryChangeRequestStore:
    store = InMemoryChangeRequestStore()
    store.record(
        ChangeRequestRecord(
            accessor=ACCESSOR,
            requester=requester,
            tenant_id=tenant,
            claim_name="groups",
            claim_value="sre",
            role="operator",
            submitted_at=datetime(2026, 7, 28, tzinfo=UTC),
        )
    )
    return store


def _collect(store: Any, status_source: Any, subject: AuthenticatedSubject) -> Any:
    return collect_mapping_change(
        accessor=ACCESSOR,
        subject=subject,
        change_requests=store,
        change_status=status_source,
        audit=InMemoryAuditSink(),
    )


def test_the_requester_learns_it_is_pending() -> None:
    """Pending is an answer, and the row that says so exists because 008 predicted the
    failure of treating a non-final state as a refusal."""
    result = _collect(_store(), StatusSource("pending"), _subject())

    assert result.disposition == "pending"
    assert result.required == 2


def test_the_requester_learns_it_was_approved_without_being_told() -> None:
    """SC-001: zero out-of-band communication. The whole point of the operation."""
    result = _collect(_store(), StatusSource("approved", approvals=2), _subject())

    assert result.disposition == "approved"


def test_polling_never_advances_the_change() -> None:
    """FR-002, and the property that matters most in this file.

    Ten collects leave the disposition where it was. The fabric is asked each time — this
    is not a cache — and asking is all that happens, because the status endpoint has no
    authorization semantics and this code knows no other endpoint.
    """
    source = StatusSource("pending")
    store = _store()

    for _ in range(10):
        assert _collect(store, source, _subject()).disposition == "pending"

    assert source.calls == 10


def test_another_tenant_is_answered_as_absent() -> None:
    """The record is what makes the accessor stop being a bearer capability.

    Vault answers whoever presents an accessor. Without the tenant-scoped record in front,
    holding one would let a caller poll another customer's request.
    """
    with pytest.raises(OperationRefused) as caught:
        _collect(_store(tenant="tenant-b"), StatusSource(), _subject(tenant="tenant-a"))

    assert caught.value.reason_code == "no_such_record"
    assert not caught.value.is_visible_to_caller


def test_someone_else_in_the_tenant_is_refused_with_a_reason() -> None:
    """They can already see it exists; hiding the reason would only confuse them."""
    with pytest.raises(OperationRefused) as caught:
        _collect(_store(requester="bob"), StatusSource(), _subject(user="alice"))

    assert caught.value.reason_code == "not_permitted"
    assert caught.value.is_visible_to_caller


def test_the_collect_is_audited() -> None:
    """FR-017. Observing a governance decision is itself observable."""
    audit = InMemoryAuditSink()
    collect_mapping_change(
        accessor=ACCESSOR,
        subject=_subject(),
        change_requests=_store(),
        change_status=StatusSource("approved"),
        audit=audit,
    )

    entries = audit.list_by_correlation_id("authority-change:tenant-a")
    assert entries, "collecting a disposition left no trace"
    assert entries[-1].payload["collected_by"] == "alice"


def test_break_fixture_a_collect_that_authorizes_is_detectable() -> None:
    """The defect this file exists to catch, constructed and shown to be visible.

    The plausible mistake is reaching for the wrong member of the fabric's control-group
    endpoint family — `authorize` rather than `request`. It would look like a working
    collect, and the change would approve itself on the first poll by whoever submitted it.

    A status source that advances on read models exactly that, and `test_polling_never_
    advances_the_change` is what fails.
    """

    class AuthorizingSource(StatusSource):
        def status_of(self, accessor: str) -> CollectedDisposition:
            self.calls += 1
            # The defect: asking changed something.
            self.approvals += 1
            self.disposition = "approved" if self.approvals >= 2 else "pending"
            return CollectedDisposition(
                accessor=accessor,
                disposition=self.disposition,
                approvals=self.approvals,
                required=2,
            )

    source = AuthorizingSource()
    store = _store()

    _collect(store, source, _subject())
    second = _collect(store, source, _subject())

    assert second.disposition == "approved", (
        "the fixture no longer models a collect that authorizes — if this changes, the "
        "polling row above has stopped being the thing that catches it"
    )
