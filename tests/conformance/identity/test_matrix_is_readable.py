# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the run role can actually read the matrix and the bindings record.

**A row rather than a Terraform review**, because the grant being present in HCL and the
grant being *effective* are two different claims. 010 learned that when the registry engine
appended policies nobody had declared, and the difference only showed up against the live
fabric.

The failure this guards is worse than "cannot read". Without the grant Vault answers **403,
not 404** — so "no matrix" becomes indistinguishable from "not allowed to look", and the
fabric reports an unreachable trust fabric for a record that merely lacks a policy line.
Whoever debugs that goes to Vault's health. The `data/policies/*` grant beside these two
documents the same trap from 010; these rows exist so it is caught by a lane rather than
rediscovered.
"""

from __future__ import annotations

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.vault_fabric import (
    DEFINITION_BINDINGS_PATH,
    MATRIX_PATH,
    VaultIdentityFabric,
)

# BOTH markers, not `host_enclave` alone. The hermetic lane filters on `-m "not
# enclave"`, which does not deselect `host_enclave` — so a row marked only host_enclave
# RUNS IN THE FAST LANE with no enclave and fails for want of a stack. `host_enclave`
# says *where* among enclave rows this must run; `enclave` says it needs one at all.
pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


def _reason(exc: ResolutionRefused) -> str:
    return str(getattr(exc, "reason_code", ""))


def test_the_run_role_may_read_the_matrix_path(fabric: VaultIdentityFabric) -> None:
    """Absent is fine. Forbidden is not.

    An empty enclave has no matrix, and this asserts the *distinction survives*: a missing
    record must refuse as a missing record, never as a permission failure, because those
    two send an operator to entirely different places.
    """
    try:
        fabric.read_matrix()
    except ResolutionRefused as exc:
        assert _reason(exc) == "missing_ceiling_record", (
            f"reading {MATRIX_PATH} refused as {_reason(exc)!r}. A permission or "
            f"reachability reason here means the grant is missing: Vault answers 403 rather "
            f"than 404, so an absent matrix is reported as a broken fabric"
        )


def test_the_run_role_may_read_the_definition_bindings_path(fabric: VaultIdentityFabric) -> None:
    try:
        fabric.resolve_definition_bindings("definitely-not-a-real-definition")
    except ResolutionRefused as exc:
        assert _reason(exc) == "missing_ceiling_record", (
            f"reading {DEFINITION_BINDINGS_PATH} refused as {_reason(exc)!r}; the same "
            f"403-not-404 trap, in the record the whole feature depends on"
        )


def test_a_fixture_definition_has_bindings_written_by_the_same_apply(
    fabric: VaultIdentityFabric,
) -> None:
    """The positive control, and the reason the Terraform uses one `for_each`.

    A definition holding a ceiling and no bindings record is the window two applies would
    open. The rows above pass against an enclave where nothing was ever written — this one
    fails if the bindings resource did not apply alongside the ceiling.
    """
    bindings = fabric.resolve_definition_bindings("planner")
    assert bindings.agent_definition_id == "planner"
    assert bindings.tier >= 1
