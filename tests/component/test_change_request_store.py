# SPDX-License-Identifier: Apache-2.0
"""Who may ask about a submitted change — the decision, without a database.

The record exists because Vault's status endpoint answers whoever presents an accessor.
`authorize_collect` is the gate in front of it, and it is a pure function precisely so
these rows can exercise every branch without an enclave.

**The two refusals differ on purpose**, and the asymmetry is the interesting part: absent
and another-tenant's collapse to the same answer, while this-tenant-but-someone-else's
names its reason. The caller in the second case can already see the change exists — the
tenant boundary already let them that far — so hiding the reason would tell them nothing
they could not infer, while costing them the ability to understand the refusal.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.runs.changes import (
    ChangeRequestRecord,
    InMemoryChangeRequestStore,
    authorize_collect,
)
from core.runs.refusals import INDISTINGUISHABLE_TO_CALLER, OperationRefused


def _record(
    *, accessor: str = "acc-1", requester: str = "alice", tenant: str = "tenant-a"
) -> ChangeRequestRecord:
    return ChangeRequestRecord(
        accessor=accessor,
        requester=requester,
        tenant_id=tenant,
        claim_name="groups",
        claim_value="sre",
        role="operator",
        submitted_at=datetime(2026, 7, 28, tzinfo=UTC),
    )


def test_the_requester_may_ask() -> None:
    """The positive control, and the whole point of the record."""
    store = InMemoryChangeRequestStore()
    store.record(_record())

    found = store.get(accessor="acc-1", tenant_id="tenant-a")

    assert authorize_collect(found, subject_user_id="alice").accessor == "acc-1"


def test_another_tenant_sees_nothing() -> None:
    """Store-level: the record is not returned, so there is nothing to authorize against.

    This is the row that makes the accessor stop being a bearer capability — the defect
    the record exists to prevent.
    """
    store = InMemoryChangeRequestStore()
    store.record(_record(tenant="tenant-b"))

    assert store.get(accessor="acc-1", tenant_id="tenant-a") is None

    with pytest.raises(OperationRefused) as caught:
        authorize_collect(None, subject_user_id="alice")
    assert caught.value.reason_code == "no_such_record"


def test_someone_else_in_the_same_tenant_is_refused_with_a_reason() -> None:
    """Named rather than collapsed, and the asymmetry is deliberate.

    They can already see it exists. Collapsing here would cost them an explanation
    without hiding anything.
    """
    store = InMemoryChangeRequestStore()
    store.record(_record(requester="bob"))

    found = store.get(accessor="acc-1", tenant_id="tenant-a")
    with pytest.raises(OperationRefused) as caught:
        authorize_collect(found, subject_user_id="alice")

    assert caught.value.reason_code == "not_permitted"
    assert caught.value.is_visible_to_caller


def test_the_absent_case_is_not_visible_to_the_caller() -> None:
    """The property the wire depends on, asserted on the exception rather than the route.

    A route that decided this for itself would eventually decide differently from another
    route, and the difference would be a probe oracle nobody meant to build.
    """
    with pytest.raises(OperationRefused) as caught:
        authorize_collect(None, subject_user_id="alice")

    assert not caught.value.is_visible_to_caller
    assert caught.value.reason_code in INDISTINGUISHABLE_TO_CALLER


def test_an_unknown_reason_code_cannot_be_invented() -> None:
    """The guard that keeps six operations refusing in one vocabulary."""
    with pytest.raises(ValueError):
        OperationRefused("something", reason_code="made_up_at_the_call_site")
