# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — collecting a real gated change's disposition (SC-001).

The hermetic rows in `tests/component/test_collect_mapping_change.py` prove the decision:
who may ask, what each refusal means, that polling advances nothing. What they cannot prove
is that the trust fabric answers the way this platform believes it does — that the accessor
Vault hands back on a queued request is the one its status endpoint accepts, and that a
real approval shows up as approved.

**`host_enclave`**, for the same reason the gated-mapping row is: setting up a Control
Group needs an admin token the allocation deliberately lacks. Collect inherits that
arrangement rather than inventing one.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from core.audit.sink import InMemoryAuditSink
from core.authority.changes import BlockedPendingApprovalError
from core.identity.claims import ClaimMapping
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.runs.changes import (
    ChangeRequestRecord,
    InMemoryChangeRequestStore,
    VaultChangeStatus,
)
from core.runs.refusals import OperationRefused
from surfaces.api.authority_submit import VaultAuthoritySubmitter
from surfaces.api.mappings import collect_mapping_change
from tests.harness.vault_control_groups import VaultAdmin, reachable

#: FR-014 — this row supplies no identity fabric at all; its subject is the trust fabric's
#: control-group behaviour, not authority resolution.
FAKE_FABRIC_IS_FAULT_INJECTION = "the trust fabric's control-group status endpoint"

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

MAPPING = ClaimMapping(claim_name="groups", claim_value="sre", role="operator")
TENANT = "tenant-conformance"


def _subject(user: str = "alice", tenant: str = TENANT) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id=user,
        tenant_id=tenant,
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


@pytest.fixture
def admin() -> VaultAdmin:
    if not reachable():
        pytest.fail(
            "the control-plane Vault is unreachable — run `make dev-up`. This row is not "
            "skippable: a collect proven only against a double has not been proven."
        )
    return VaultAdmin()


@pytest.fixture
def gated(admin: VaultAdmin) -> Iterator[dict[str, str]]:
    """A Control-Group-gated path, torn down afterwards."""
    suffix = uuid.uuid4().hex[:8]
    mount, group, policy = (
        f"cg-collect-{suffix}",
        f"cg-collect-approvers-{suffix}",
        f"cg-collect-writer-{suffix}",
    )
    admin.request(f"sys/mounts/{mount}", {"type": "kv", "options": {"version": "2"}})
    admin.request("identity/group", {"name": group, "type": "internal"})
    admin.request(
        f"sys/policies/acl/{policy}",
        {
            "policy": (
                f'path "{mount}/*" {{\n'
                '  capabilities = ["create", "update", "read"]\n'
                "  control_group = {\n"
                '    factor "approvers" {\n'
                "      identity {\n"
                f'        group_names = ["{group}"]\n'
                "        approvals   = 2\n"
                "      }\n"
                "    }\n"
                "  }\n"
                "}\n"
            )
        },
    )
    yield {"mount": mount, "group": group, "policy": policy}
    admin.request(f"sys/mounts/{mount}", method="DELETE")
    admin.request(f"sys/policies/acl/{policy}", method="DELETE")
    admin.request(f"identity/group/name/{group}", method="DELETE")


def _queue(admin: VaultAdmin, gated: dict[str, str], path: str) -> str:
    """Submit a change that gates, and return the accessor Vault handed back."""
    submitter = VaultAuthoritySubmitter(
        vault_addr=admin.addr,
        controlled_path=f"{gated['mount']}/data/{path}",
        token=admin.token_for(gated["policy"]),
        cacert=admin.cacert or None,
    )
    with pytest.raises(BlockedPendingApprovalError) as pending:
        submitter.submit(requester="alice", mapping=MAPPING)
    accessor = pending.value.accessor
    assert accessor, "queued with no accessor — the outcome is uncollectable"
    return str(accessor)


def _store(
    accessor: str, *, requester: str = "alice", tenant: str = TENANT
) -> InMemoryChangeRequestStore:
    store = InMemoryChangeRequestStore()
    store.record(
        ChangeRequestRecord(
            accessor=accessor,
            requester=requester,
            tenant_id=tenant,
            claim_name=MAPPING.claim_name,
            claim_value=MAPPING.claim_value,
            role=MAPPING.role,
            submitted_at=datetime.now(UTC),
        )
    )
    return store


def _status(admin: VaultAdmin) -> VaultChangeStatus:
    return VaultChangeStatus(vault_addr=admin.addr, token=admin.token, cacert=admin.cacert or None)


def test_row_a_queued_change_reads_as_pending(admin: VaultAdmin, gated: dict[str, str]) -> None:
    """The accessor Vault hands back is one its status endpoint accepts.

    That is the claim a double cannot make: the hermetic rows assume the two agree, and
    this is where the assumption is checked.
    """
    accessor = _queue(admin, gated, "mapping-collect-a")

    disposition = collect_mapping_change(
        accessor=accessor,
        subject=_subject(),
        change_requests=_store(accessor),
        change_status=_status(admin),
        audit=InMemoryAuditSink(),
    )

    assert disposition.disposition == "pending"
    # The path the queued change would write, which is how a person confirms the thing
    # waiting for approval is the thing they asked for.
    assert gated["mount"] in disposition.request_path
    assert disposition.approvals == 0, "nobody has approved yet, so nobody should be counted"


def test_row_polling_a_real_change_never_advances_it(
    admin: VaultAdmin, gated: dict[str, str]
) -> None:
    """FR-002 against the real endpoint.

    The break fixture in the hermetic file models a collect that authorizes; this proves
    the endpoint this code actually calls is not that one. Five polls, still pending.
    """
    accessor = _queue(admin, gated, "mapping-collect-b")
    store, status = _store(accessor), _status(admin)

    for _ in range(5):
        result = collect_mapping_change(
            accessor=accessor,
            subject=_subject(),
            change_requests=store,
            change_status=status,
            audit=InMemoryAuditSink(),
        )
        assert result.disposition == "pending"

    # And the gated value is still absent — polling did not partially apply it either.
    code, _ = admin.request(f"{gated['mount']}/data/mapping-collect-b", method="GET")
    assert code == 404


def test_row_another_tenant_cannot_collect_a_real_accessor(
    admin: VaultAdmin, gated: dict[str, str]
) -> None:
    """The record is what stops a valid accessor being a bearer capability.

    Vault would answer this caller happily — it answers whoever presents an accessor. The
    refusal comes from our record, which is the whole reason it exists.
    """
    accessor = _queue(admin, gated, "mapping-collect-c")

    with pytest.raises(OperationRefused) as caught:
        collect_mapping_change(
            accessor=accessor,
            subject=_subject(tenant="tenant-somebody-else"),
            change_requests=_store(accessor, tenant=TENANT),
            change_status=_status(admin),
            audit=InMemoryAuditSink(),
        )

    assert caught.value.reason_code == "no_such_record"


def test_row_an_unknown_accessor_reads_as_absent_not_as_an_outage(admin: VaultAdmin) -> None:
    """The 400-with-'invalid accessor' shape, asserted against the fabric itself.

    Probed during planning and asserted here, because it is engine-specific: the registry
    answers 400 for a missing definition while KV answers 404, and a reader that
    generalised would report an outage for a change that simply never existed.
    """
    bogus = f"nonexistent-{uuid.uuid4().hex[:8]}"

    with pytest.raises(OperationRefused) as caught:
        collect_mapping_change(
            accessor=bogus,
            subject=_subject(),
            change_requests=_store(bogus),
            change_status=_status(admin),
            audit=InMemoryAuditSink(),
        )

    assert caught.value.reason_code == "no_such_record"
