# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the matrix and bindings grants are EFFECTIVE, not merely written.

**A row rather than a Terraform review**, because a grant present in HCL and a grant that is
effective are different claims — 010 learned that when the registry engine appended policies
nobody had declared.

**Read as the operator, deliberately** (the 011 posture): the first version of these rows
used the workload-identity fabric and failed with `CredentialUnavailableError`, because a
host process holds no attested identity — that is a property the platform is built on, not a
test inconvenience. So the host asserts what an operator can: the run role's policy **as
applied in Vault** grants the two paths, and the bindings record **exists** for the fixture
definitions. The run-role read itself is exercised where the run role exists — in an
allocation, by the dispatch row in `test_pack_tools_dispatch.py`, whose entrypoint resolves
authority under its own identity.

The failure these guard is the 403-not-404 trap: without the grant, "no matrix" is
indistinguishable from "not allowed to look", and the fabric reports an unreachable trust
fabric for a record that merely lacks a policy line.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Any

import pytest

# BOTH markers: `-m "not enclave"` does not deselect host_enclave alone, and a
# host_enclave-only row runs in the fast lane with no stack.
pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


def _vault(path: str) -> dict[str, Any] | None:
    """An operator read. Requires the coordinates `make conformance` passes from .env."""
    addr = (os.environ.get("VAULT_ADDR") or "").rstrip("/")
    token = os.environ.get("VAULT_TOKEN") or os.environ.get("VAULT_ROOT_TOKEN")
    if not addr or not token:
        pytest.fail(
            "these rows read Vault as the operator and VAULT_ADDR/VAULT_TOKEN are not "
            "set. `make conformance` passes them from .env. Not skippable — a row that "
            "skips itself reports the same green as one that ran."
        )
    cacert = os.environ.get("VAULT_CACERT")
    context = ssl.create_default_context(cafile=cacert) if cacert else None
    request = urllib.request.Request(  # noqa: S310 — operator-supplied addr, fixed scheme
        f"{addr}/v1/{path}", headers={"X-Vault-Token": token}
    )
    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:  # noqa: S310
            body: dict[str, Any] = json.loads(response.read())
            return body
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def test_the_run_roles_policy_grants_the_matrix_and_bindings_paths() -> None:
    """The grant as APPLIED — read back from Vault, not from policies.tf.

    This is exactly the distinction 010 paid for: HCL that says `read` and a Vault whose
    policy store contains it are two systems, and only the second decides a request.
    """
    body = _vault("sys/policy/harness-authority-read")
    assert body is not None, "the harness-authority-read policy does not exist in Vault"
    rules = str(body.get("rules", "") or body.get("data", {}).get("rules", ""))

    # 026 adds `data/ask-bindings` — the record naming which qualified cell an ask may use.
    # Same trap, same grant, same reason: without it Vault answers 403, and an absent binding
    # would present as an unreachable fabric rather than as an unbound source. The two send an
    # operator to different places, and 026's own refusal vocabulary exists to keep them apart —
    # which a missing grant would silently undo.
    for path in ("data/model-matrix", "data/definition-bindings", "data/ask-bindings"):
        assert path in rules, (
            f"the applied harness-authority-read policy does not grant {path!r}. Without "
            f"it Vault answers 403 rather than 404, so an absent record reports as a "
            f"broken trust fabric — the exact trap the data/policies/* grant documents"
        )


def test_the_bindings_record_was_written_by_the_same_apply_as_the_ceiling() -> None:
    """One `for_each`, no window. A definition holding a ceiling and no bindings record is
    what two applies would produce, and it presents as an outage with no cause."""
    for definition in ("planner-agent", "vault-agent"):
        ceiling = _vault(f"harness-authority/data/harness-ceilings/{definition}")
        bindings = _vault(f"harness-authority/data/definition-bindings/{definition}")
        assert ceiling is not None, f"{definition} has no ceiling record"
        assert bindings is not None, (
            f"{definition} has a ceiling and no bindings record; the Terraform writes both "
            f"from one for_each precisely so this state cannot exist"
        )


def test_the_vault_agents_bindings_carry_the_pack() -> None:
    """The record the whole feature reads, holding the values the apply declared."""
    body = _vault("harness-authority/data/definition-bindings/vault-agent")
    assert body is not None
    data = body.get("data", {}).get("data", {})
    assert data.get("packs") == ["vault"]
    assert data.get("tier") == 1
    assert data.get("schema_version") == 1
