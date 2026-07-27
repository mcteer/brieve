# SPDX-License-Identifier: Apache-2.0
"""Row: a claim-to-role mapping change is gated by a REAL Control Group (FR-013).

Against the control-plane Vault, under a **non-root** token, because root bypasses Control
Groups entirely — verified in 007, and the reason the production profile revokes its
bootstrap credential.

There is no fake here and there cannot be a useful one. A double that always returns
"pending" proves the caller handles pending; one that always denies proves it handles
denial; neither proves the gate holds, which is the only claim FR-013 makes. The component
tests cover how the surface *reports* a disposition; this covers whether anything was
actually gated.

Note what an earlier version of this feature shipped: a `_submit` that raised pending
unconditionally without contacting Vault. Every surface test passed, the row read green,
and nothing had been submitted anywhere.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from core.authority.changes import BlockedPendingApprovalError, ChangeDisposition
from core.identity.claims import ClaimMapping
from surfaces.api.authority_submit import AuthorityChangeRefused, VaultAuthoritySubmitter
from tests.harness.vault_control_groups import VaultAdmin, reachable

# Sets up a Control Group with an admin token, which the allocation deliberately
# lacks — no token in that jobspec is the property it exists to demonstrate.
pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

MAPPING = ClaimMapping(claim_name="groups", claim_value="sre", role="operator")


@pytest.fixture
def admin() -> VaultAdmin:
    if not reachable():
        pytest.fail(
            "the control-plane Vault is unreachable — run `make dev-up`. This row is not "
            "skippable: a gate nobody exercised is a gate nobody knows holds."
        )
    return VaultAdmin()


@pytest.fixture
def gated(admin: VaultAdmin) -> Iterator[dict[str, str]]:
    """A path gated by a real Control Group, torn down afterwards.

    Deliberately not the paths the deployment tree manages — gating those would require
    approvals to run the tree that manages the environment this test runs in.
    """
    suffix = uuid.uuid4().hex[:8]
    mount = f"cg-mapping-{suffix}"
    group = f"cg-mapping-approvers-{suffix}"
    policy = f"cg-mapping-writer-{suffix}"

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


def _submitter(admin: VaultAdmin, gated: dict[str, str], path: str) -> VaultAuthoritySubmitter:
    return VaultAuthoritySubmitter(
        vault_addr=admin.addr,
        controlled_path=f"{gated['mount']}/data/{path}",
        token=admin.token_for(gated["policy"]),
        cacert=admin.cacert or None,
    )


def test_row_a_mapping_change_is_queued_not_applied(
    admin: VaultAdmin, gated: dict[str, str]
) -> None:
    """The submitter reports pending, and the change has not happened."""
    submitter = _submitter(admin, gated, "mapping-a")

    with pytest.raises(BlockedPendingApprovalError) as pending:
        submitter.submit(requester="alice", mapping=MAPPING)

    # A wrapping token means Vault queued it. Without an accessor there is nothing for the
    # requester to collect the outcome with, which would make "pending" a dead end.
    assert pending.value.accessor, "queued with no accessor — the outcome is uncollectable"

    # The assertion that matters: read as admin and the value is absent. A pending request
    # must not be a partially applied one.
    status, _ = admin.request(f"{gated['mount']}/data/mapping-a", method="GET")
    assert status == 404, "the mapping changed before quorum was reached"


def test_row_pending_is_not_a_denial(admin: VaultAdmin, gated: dict[str, str]) -> None:
    """Vault distinguishes them natively; the submitter must not flatten them.

    Collapsed together, a client either retries forever or reports a failure that has not
    happened — and at an HTTP surface the wrong choice is sticky.
    """
    pending_submitter = _submitter(admin, gated, "mapping-b")
    with pytest.raises(BlockedPendingApprovalError):
        pending_submitter.submit(requester="alice", mapping=MAPPING)

    # An ungranted path is refused outright rather than queued.
    denied = VaultAuthoritySubmitter(
        vault_addr=admin.addr,
        controlled_path="sys/policies/acl/some-path-this-token-cannot-write",
        token=admin.token_for(gated["policy"]),
        cacert=admin.cacert or None,
    )
    with pytest.raises(AuthorityChangeRefused):
        denied.submit(requester="alice", mapping=MAPPING)


def test_row_an_ungated_path_applies_rather_than_queueing(
    admin: VaultAdmin, gated: dict[str, str]
) -> None:
    """The control: the submitter is not simply reporting 'pending' for everything.

    Without this, a submitter that raised pending unconditionally — which is exactly what
    this feature shipped at first — would satisfy every assertion above.
    """
    ungated_mount = f"{gated['mount']}-ungated"
    admin.request(f"sys/mounts/{ungated_mount}", {"type": "kv", "options": {"version": "2"}})
    try:
        submitter = VaultAuthoritySubmitter(
            vault_addr=admin.addr,
            controlled_path=f"{ungated_mount}/data/mapping-c",
            token=admin.token,
            cacert=admin.cacert or None,
        )
        assert submitter.submit(requester="alice", mapping=MAPPING) is ChangeDisposition.APPROVED

        status, _ = admin.request(f"{ungated_mount}/data/mapping-c", method="GET")
        assert status == 200, "an ungated write should have taken effect"
    finally:
        admin.request(f"sys/mounts/{ungated_mount}", method="DELETE")


def test_row_wrap_info_truthiness_not_key_presence(
    admin: VaultAdmin, gated: dict[str, str]
) -> None:
    """`wrap_info` is a key with value null on every Vault response.

    007 lost three tests to this: `"wrap_info" in body` is true for all inputs, so the
    assertion passed regardless of behaviour. This row asserts the raw shape directly so
    the trap is visible where someone might reintroduce it.
    """
    token = admin.token_for(gated["policy"])
    _, ungated_body = admin.request("auth/token/lookup-self", method="GET", token=token)
    assert "wrap_info" in ungated_body, "expected the key to be present on an ordinary response"
    assert not ungated_body.get("wrap_info"), "and to be falsy — key presence proves nothing"
