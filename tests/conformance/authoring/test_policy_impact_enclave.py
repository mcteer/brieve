# SPDX-License-Identifier: Apache-2.0
"""V15-V17 — the instrument against the REAL Vault (042, FR-016, SC-007/010/012).

**The whole claim of this feature is that the impact check is real.** Every hermetic row above
drives a scripted Vault that answers from the policy it was handed — which proves the
handler's sequencing and arithmetic and proves nothing about whether the product agrees. A
fixture that reports its own cleanup is not evidence of cleanup, and ADR-0047 is what this
estate does about that.

**These fail rather than skip.** A lane that skips reads as green, and "validated" would then
mean "not checked" (FR-016, SC-007). Named runner: **Dan, before merge**, per constitution
v1.1.0 and the feature's conformance contract.

**V16 is the row that tests the layer nothing else can.** It disables the platform's
governance hook and asks Vault directly for a protected policy name. The refusal must come
from the product — the only layer that survives a bug in everything this repository owns.
"""

from __future__ import annotations

import os

import pytest

from core.durability.credentials import VaultDatabaseCredentials, VaultReadFailed
from surfaces.mcp.scratch_sweep import sweep_scratch_policies

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

RUN = "corr-042-enclave"
CURRENT = 'path "secret/data/payments/*" {\n  capabilities = ["read"]\n}\n'
WIDER = 'path "secret/data/payments/*" {\n  capabilities = ["read", "create", "update"]\n}\n'


class _RootIdentity:
    """The operator token, for a row that must arrange and inspect real Vault state.

    Deliberately NOT the run's identity: these rows verify what a dispatched run may do, and
    an inspector holding the same bounded token could not tell "the policy is gone" from "I
    may not see it".
    """

    def jwt(self) -> str:  # pragma: no cover — never used; the token is passed directly
        raise AssertionError("root identity does not present a JWT")


@pytest.fixture
def vault() -> VaultDatabaseCredentials:
    """A client pointed at the enclave, or a failure that says what is missing."""
    token = os.environ.get("VAULT_TOKEN", "").strip()
    if not token:
        pytest.fail(
            "VAULT_TOKEN is unset. These rows measure against the real Vault and cannot "
            "invent one; they fail rather than skip (FR-016, SC-007). Run `make dev-up` and "
            "export the root token."
        )
    client = VaultDatabaseCredentials(
        identity=_RootIdentity(), vault_addr=os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200")
    )
    client.login = lambda: token  # type: ignore[method-assign]
    return client


def _policy_names(vault: VaultDatabaseCredentials) -> list[str]:
    return vault.list_path("sys/policies/acl") or []


def test_row_v15_the_full_scratch_lifecycle_runs_and_leaves_nothing(
    vault: VaultDatabaseCredentials,
) -> None:
    """V15 — write both sides, ask Vault, destroy both. Zero survivors (SC-010).

    The capability answer is the product's, which is the property no fixture can stand in for:
    this row would fail if Vault's semantics for a glob path, a KV v2 `data/` prefix, or a
    capability name differed from what the handler assumes.
    """
    proposed = f"scratch-agent-{RUN}-proposed"
    current = f"scratch-agent-{RUN}-current"

    vault.write_path(f"sys/policies/acl/{current}", {"policy": CURRENT})
    vault.write_path(f"sys/policies/acl/{proposed}", {"policy": WIDER})
    try:
        before = vault.create_token(role="scratch-check", policies=[current], ttl="60s", token=None)
        after = vault.create_token(role="scratch-check", policies=[proposed], ttl="60s")

        current_caps = vault.capabilities(subject_token=before, paths=["secret/data/payments/app"])
        proposed_caps = vault.capabilities(subject_token=after, paths=["secret/data/payments/app"])
    finally:
        vault.delete_path(f"sys/policies/acl/{proposed}")
        vault.delete_path(f"sys/policies/acl/{current}")

    granted = set(proposed_caps["secret/data/payments/app"]) - set(
        current_caps["secret/data/payments/app"]
    )
    assert {"create", "update"} <= granted, (
        f"Vault reported {proposed_caps} against {current_caps}; the widening this row "
        f"proposes must be visible in the product's own answer"
    )

    surviving = [n for n in _policy_names(vault) if n.startswith(f"scratch-agent-{RUN}")]
    assert not surviving, f"{surviving} outlived the measurement (SC-010)"


def test_row_v16_vaults_own_acl_refuses_a_protected_name(
    vault: VaultDatabaseCredentials,
) -> None:
    """V16 — the back-stop, tested with the platform's hook out of the way (SC-012).

    Every other refusal in this feature is the platform's. This one is the product's: even
    with `protected_policy_hook` unregistered and the request check bypassed — which is
    exactly what this row does by calling the client directly — the token role's
    `allowed_policies_glob` admits nothing but `scratch-agent-*`.

    A back-stop only ever exercised behind a working front-stop has never been tested.
    """
    with pytest.raises(VaultReadFailed) as raised:
        vault.create_token(role="scratch-check", policies=["agent-ceiling"], ttl="60s")

    assert raised.value.status in (400, 403), (
        f"Vault answered {raised.value.status} minting a token under `agent-ceiling`; the "
        f"token role must refuse a policy outside the measurement namespace"
    )


def test_row_v16_a_run_may_not_write_a_protected_policy_directly(
    vault: VaultDatabaseCredentials,
) -> None:
    """The other half of the product-level bound: the ACL, not just the token role.

    This uses the RUN's grant rather than the operator token — the point is what a dispatched
    run can reach, and the operator can obviously write anything.
    """
    run_client = VaultDatabaseCredentials(
        identity=_RootIdentity(),
        vault_addr=os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200"),
    )
    scratch_only = vault.create_token(
        role="scratch-check", policies=[f"scratch-agent-{RUN}-probe"], ttl="60s"
    )
    run_client.login = lambda: scratch_only  # type: ignore[method-assign]

    with pytest.raises(VaultReadFailed):
        run_client.write_path("sys/policies/acl/agent-ceiling", {"policy": 'path "*" {}'})


def test_row_v17_an_orphan_is_swept_and_the_removal_is_audited(
    vault: VaultDatabaseCredentials,
) -> None:
    """V17 — FR-023, with the orphan PLANTED rather than waited for.

    "Always destroyed" is a claim; the sweep is what makes it checkable. Planting the orphan
    is what makes the row deterministic — waiting for a real kill would be a test that passes
    by not having noticed anything.
    """
    from core.audit.sink import InMemoryAuditSink

    orphan = f"scratch-agent-{RUN}-orphan-proposed"
    vault.write_path(f"sys/policies/acl/{orphan}", {"policy": CURRENT})
    assert orphan in _policy_names(vault), "the orphan was not planted; the row proves nothing"

    audit = InMemoryAuditSink()
    outcome = sweep_scratch_policies(
        list_policies=lambda: _policy_names(vault),
        delete_policy=vault.delete_path,
        is_live=lambda run_id: False,
        audit=audit,
        tenant_id="tenant-test",
    )

    assert orphan in outcome.removed
    assert orphan not in _policy_names(vault)
    assert [
        e for e in audit.all_entries() if e.payload.get("code") == "orphaned_scratch_policy_removed"
    ], "a policy vanished from the trust fabric with no record"
