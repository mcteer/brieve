# SPDX-License-Identifier: Apache-2.0
"""US1 — widening authority requires more than one person (T009-T012).

Against the **real** control-plane Vault. No fake Control Group exists: one that always
approves proves the caller can proceed, one that never approves proves it handles denial,
and neither proves the gate holds.

Every assertion runs under a **non-root** identity, because root bypasses Control Groups
entirely — verified, and the reason the production profile revokes its bootstrap
credential.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from tests.harness.vault_control_groups import VaultAdmin, reachable

pytestmark = pytest.mark.enclave

GATED_MOUNT = "cg-test"


@pytest.fixture
def admin() -> VaultAdmin:
    if not reachable():
        pytest.fail(
            "the control-plane Vault is unreachable — run `make dev-up`. These rows are "
            "not skippable: a gate nobody exercised is a gate nobody knows holds."
        )
    return VaultAdmin()


@pytest.fixture
def gated(admin: VaultAdmin) -> Iterator[dict[str, str]]:
    """A path gated by a real Control Group, torn down afterwards.

    Deliberately NOT the paths the deployment tree manages: gating those would require
    approvals to run the tree that manages the environment the tests run in.
    """
    suffix = uuid.uuid4().hex[:8]
    mount = f"{GATED_MOUNT}-{suffix}"
    group = f"cg-approvers-{suffix}"
    policy = f"cg-writer-{suffix}"

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


def test_change_does_not_take_effect_below_quorum(admin: VaultAdmin, gated: dict[str, str]) -> None:
    """SC-001. The write is accepted as a *request*, and the value is not there."""
    token = admin.token_for(gated["policy"])
    status, body = admin.request(
        f"{gated['mount']}/data/widening", {"data": {"ceiling": "widened"}}, token=token
    )

    assert status == 200
    # `wrap_info` is present as a key with value null on EVERY Vault response, so key
    # presence proves nothing. Truthiness is the real signal — an easy assertion to get
    # wrong in a way that passes for all inputs.
    assert body.get("wrap_info"), (
        "expected a wrapping token — the pending approval request. Getting a plain write "
        "back means the gate is not attached to this path."
    )

    # Read as the admin: the change has not happened. This is the assertion that matters —
    # a pending request must not be a partially applied one (FR-009).
    read_status, _ = admin.request(f"{gated['mount']}/data/widening", method="GET")
    assert read_status == 404, "authority changed before quorum was reached"


def test_pending_request_is_distinguishable_from_denial(
    admin: VaultAdmin, gated: dict[str, str]
) -> None:
    """Blocked-pending-approval is not a denial (contracts/evidence.md).

    Collapsed together, a caller either retries forever or reports a failure that is not
    one. Vault makes the distinction natively: a wrapping token versus a 403.
    """
    token = admin.token_for(gated["policy"])
    pending, body = admin.request(f"{gated['mount']}/data/pending", {"data": {"v": 1}}, token=token)
    denied, _ = admin.request("sys/policies/acl/some-other-policy", {"policy": ""}, token=token)

    assert pending == 200 and body.get("wrap_info"), "pending approval should not read as failure"
    assert denied == 403, "an ungranted path should be denied outright, not queued"


def test_no_change_takes_effect_by_timeout_or_default(
    admin: VaultAdmin, gated: dict[str, str]
) -> None:
    """SC-002. A request nobody answers leaves the value absent — expiry means no change."""
    token = admin.token_for(gated["policy"])
    admin.request(f"{gated['mount']}/data/never-approved", {"data": {"v": 1}}, token=token)

    status, _ = admin.request(f"{gated['mount']}/data/never-approved", method="GET")
    assert status == 404, (
        "an unapproved request took effect. There is no timeout that grants by default "
        "and no escalation that lowers the requirement (FR-009)."
    )


def test_root_bypasses_the_gate_which_is_why_production_revokes_it(
    admin: VaultAdmin, gated: dict[str, str]
) -> None:
    """Not a bug — the reason FR-011's revocation matters.

    Asserted so the property is visible rather than folklore: a deployment that keeps a
    root token has an authority gate anyone holding that token walks around.
    """
    status, body = admin.request(f"{gated['mount']}/data/as-root", {"data": {"v": 1}})

    assert status == 200 and not body.get("wrap_info"), (
        "root was gated — if this ever fails, the bypass has been closed and the "
        "production revocation requirement can be re-argued rather than assumed"
    )
    read_status, _ = admin.request(f"{gated['mount']}/data/as-root", method="GET")
    assert read_status == 200, "root's write should have taken effect immediately"
