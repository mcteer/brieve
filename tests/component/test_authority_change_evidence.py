# SPDX-License-Identifier: Apache-2.0
"""US1 evidence, and US4/US5 boundaries (T015, T016, T023-T027).

Evidence first: an authority change is the highest-consequence write in the system, so
what must be reconstructable afterwards is a requirement rather than a nicety.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime

import pytest

from core.authority import changes as changes_module
from core.authority.changes import (
    AuthorityChangeEvent,
    BlockedPendingApprovalError,
    ChangeDisposition,
    observe_change,
)
from tests.harness import assert_no_secret_values
from tests.harness.vault_control_groups import VaultAdmin, reachable


def test_evidence_carries_who_what_and_outcome() -> None:
    """FR-011, SC-008. Joined by correlation ID, or an investigator correlates by hand."""
    event = observe_change(
        correlation_id="corr-1",
        controlled_path="sys/policies/acl/agent-ceiling-demo",
        disposition=ChangeDisposition.APPROVED,
        identities=["alice", "bob"],
        occurred_at=datetime.now(UTC),
    )
    dumped = event.public_dict()

    assert dumped["correlation_id"] == "corr-1"
    assert dumped["disposition"] == "approved"
    assert dumped["identities"] == ["alice", "bob"]
    assert_no_secret_values(dumped)


def test_evidence_holds_no_credential_or_policy_content() -> None:
    """An audit record of an authority change is not a place to copy the authority."""
    fields = set(AuthorityChangeEvent.model_fields)
    assert not fields & {"policy", "token", "credential", "secret", "approvals_state"}


def test_blocked_pending_approval_is_not_a_denial() -> None:
    """contracts/evidence.md. Vault distinguishes them natively; the seam must not flatten
    that, or a caller retries forever or reports a failure that has not happened."""
    err = BlockedPendingApprovalError(accessor="acc-1")
    assert err.reason_code == "blocked_pending_approval"
    assert "denied" not in err.reason_code
    assert err.accessor == "acc-1"


def test_the_harness_evaluates_nothing() -> None:
    """FR-014 at the source level. Vault decides; this module witnesses.

    A quorum computation appearing here is the signal that a second decision-maker has
    grown beside the trust fabric.
    """
    source = inspect.getsource(changes_module)
    for forbidden in ("required_approvals", "quorum_met", "len(approvals)", "authorized_approvers"):
        assert forbidden not in source, (
            f"{forbidden!r} suggests the harness is evaluating quorum. It must only observe."
        )


def test_no_disposition_means_waiting_on_a_human() -> None:
    """FR-012 from the evidence side. A run must never observe a state that means a person
    is deciding."""
    for disposition in ChangeDisposition:
        assert disposition.value in {"requested", "approved", "denied", "expired"}


# --------------------------------------------------------------- US4 / US5 against Vault


@pytest.fixture
def admin() -> VaultAdmin:
    if not reachable():
        pytest.fail("the control-plane Vault is unreachable — run `make dev-up`")
    return VaultAdmin()


@pytest.mark.enclave
def test_operating_within_an_approved_definition_is_not_gated(admin: VaultAdmin) -> None:
    """US5, SC-006. The counterweight.

    Gating routine operations would train people to approve without reading, which
    destroys the gate that matters.
    """
    suffix = uuid.uuid4().hex[:8]
    mount = f"cg-instances-{suffix}"
    policy = f"cg-instance-ops-{suffix}"
    admin.request(f"sys/mounts/{mount}", {"type": "kv", "options": {"version": "2"}})
    admin.request(
        f"sys/policies/acl/{policy}",
        {"policy": f'path "{mount}/*" {{ capabilities = ["create", "update", "read"] }}\n'},
    )
    try:
        operator = admin.token_for(policy)
        status, body = admin.request(
            f"{mount}/data/instance-restart", {"data": {"action": "restart"}}, token=operator
        )
        assert status == 200
        assert not body.get("wrap_info"), (
            "an instance operation was queued for approval. The approval already happened, "
            "at the definition (FR-005)."
        )
        assert admin.request(f"{mount}/data/instance-restart", method="GET")[0] == 200
    finally:
        admin.request(f"sys/mounts/{mount}", method="DELETE")
        admin.request(f"sys/policies/acl/{policy}", method="DELETE")
