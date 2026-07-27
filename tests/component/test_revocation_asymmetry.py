# SPDX-License-Identifier: Apache-2.0
"""US2 + US3 — revocation is unilateral; restoration is not (T017-T022).

The asymmetry **is** the control. A gate that makes revoking as slow as granting is one
people route around during an incident — and then the routing-around becomes the normal
path, at which point the gate protects nothing.

Both halves live in one module because they are one property: easy to make safe, hard to
make permissive. Testing either alone would pass against a symmetric design.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from tests.harness.vault_control_groups import VaultAdmin, reachable

pytestmark = pytest.mark.enclave


@pytest.fixture
def admin() -> VaultAdmin:
    if not reachable():
        pytest.fail("the control-plane Vault is unreachable — run `make dev-up`")
    return VaultAdmin()


@pytest.fixture
def scenario(admin: VaultAdmin) -> Iterator[dict[str, str]]:
    """A mount where *writes* are gated and *deletes* are not — the asymmetry, expressed."""
    suffix = uuid.uuid4().hex[:8]
    mount, group = f"cg-revoke-{suffix}", f"cg-approvers-{suffix}"
    restore_policy, revoke_policy = f"cg-restore-{suffix}", f"cg-revoke-{suffix}"

    admin.request(f"sys/mounts/{mount}", {"type": "kv", "options": {"version": "2"}})
    admin.request("identity/group", {"name": group, "type": "internal"})

    # Restoring is gated.
    admin.request(
        f"sys/policies/acl/{restore_policy}",
        {
            "policy": (
                f'path "{mount}/*" {{\n'
                '  capabilities = ["create", "update"]\n'
                "  control_group = {\n"
                '    factor "approvers" {\n'
                f'      identity {{ group_names = ["{group}"] approvals = 2 }}\n'
                "    }\n"
                "  }\n"
                "}\n"
            )
        },
    )
    # Revoking is not. No control_group stanza, deliberately.
    admin.request(
        f"sys/policies/acl/{revoke_policy}",
        {"policy": f'path "{mount}/*" {{ capabilities = ["delete", "read", "list"] }}\n'},
    )

    yield {"mount": mount, "group": group, "restore": restore_policy, "revoke": revoke_policy}

    admin.request(f"sys/mounts/{mount}", method="DELETE")
    for p in (restore_policy, revoke_policy):
        admin.request(f"sys/policies/acl/{p}", method="DELETE")
    admin.request(f"identity/group/name/{group}", method="DELETE")


def test_revocation_is_immediate_and_needs_no_approval(
    admin: VaultAdmin, scenario: dict[str, str]
) -> None:
    """SC-004. One authorized identity, alone, immediately."""
    admin.request(f"{scenario['mount']}/data/access", {"data": {"granted": True}})
    assert admin.request(f"{scenario['mount']}/data/access", method="GET")[0] == 200

    revoker = admin.token_for(scenario["revoke"])
    status, body = admin.request(
        f"{scenario['mount']}/metadata/access", method="DELETE", token=revoker
    )

    assert status in (200, 204), f"revocation was refused: {body}"
    assert not body.get("wrap_info"), "revocation was queued for approval — it must not be"
    assert admin.request(f"{scenario['mount']}/data/access", method="GET")[0] == 404, (
        "revocation did not take effect immediately"
    )


def test_restoration_by_one_person_does_not_take_effect(
    admin: VaultAdmin, scenario: dict[str, str]
) -> None:
    """SC-005. The gated half."""
    restorer = admin.token_for(scenario["restore"])
    status, body = admin.request(
        f"{scenario['mount']}/data/access", {"data": {"granted": True}}, token=restorer
    )

    assert status == 200 and body.get("wrap_info"), "restoration was not gated"
    assert admin.request(f"{scenario['mount']}/data/access", method="GET")[0] == 404, (
        "authority was restored without quorum"
    )


def test_the_asymmetry_holds_in_both_directions(
    admin: VaultAdmin, scenario: dict[str, str]
) -> None:
    """The property neither test proves alone.

    A symmetric design — both gated, or neither — would pass one of the tests above. Only
    comparing them shows the control is asymmetric on purpose.
    """
    revoker = admin.token_for(scenario["revoke"])
    restorer = admin.token_for(scenario["restore"])

    admin.request(f"{scenario['mount']}/data/x", {"data": {"v": 1}})
    revoked, revoke_body = admin.request(
        f"{scenario['mount']}/metadata/x", method="DELETE", token=revoker
    )
    _, restore_body = admin.request(
        f"{scenario['mount']}/data/x", {"data": {"v": 1}}, token=restorer
    )

    assert revoked in (200, 204) and not revoke_body.get("wrap_info"), "revocation was gated"
    assert restore_body.get("wrap_info"), "restoration was not gated"
