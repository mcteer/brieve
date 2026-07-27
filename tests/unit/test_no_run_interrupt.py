# SPDX-License-Identifier: Apache-2.0
"""The things 007 must NOT do (T028-T032).

Negative requirements are the ones that quietly stop being true. Nobody notices the day a
pause is added — a failing test does. A feature whose subject is *humans authorizing* is
exactly where a run-time interrupt grows back, so it is asserted rather than intended.

These run without the enclave: they are properties of the source, not of a deployment.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import core.run as run_module
import core.tools.invoke as invoke_module
from core.run import RunState

INFRA = Path(__file__).resolve().parents[2] / "infra" / "modules" / "trust-fabric"


def test_no_run_state_means_awaiting_authority_change() -> None:
    """FR-012. There is no state a run enters because a human is deciding something.

    005's PARKED exists for consent and observation, both of which ADR-0049 is reshaping.
    Whatever survives, none of it may mean "an authority change is pending".
    """
    for state in RunState:
        assert "approval" not in state.value
        assert "pending" not in state.value
        assert "await" not in state.value


def test_the_invoke_path_knows_nothing_about_approvals() -> None:
    """SC-009. The governed path is where a pause would have to live, so look there.

    Control Groups gate what an agent may BECOME; hooks gate what it DOES. If approval
    vocabulary appears on the invoke path, those two have been conflated.
    """
    source = inspect.getsource(invoke_module) + inspect.getsource(run_module)
    for forbidden in ("control_group", "approval", "quorum", "authorizations"):
        assert forbidden not in source, (
            f"{forbidden!r} reached the run path. Control Groups gate what an agent may "
            "become; they must never gate what a running agent does."
        )


def test_the_gate_configuration_never_references_a_run() -> None:
    """The same property from the other side.

    A gate that could name a run is one step from pausing it.
    """
    if not INFRA.is_dir():
        return
    for tf in INFRA.glob("*.tf"):
        # Strip comments first. Prose explaining *why* the checkpoint store is not in an
        # agent's ceiling is not a reference to it — and a check that cannot tell the
        # difference gets deleted by the third person it annoys.
        code = "\n".join(line.split("#", 1)[0] for line in tf.read_text().splitlines()).lower()
        for forbidden in ("run_id", "runstate", "invoke_tool", "checkpoint"):
            assert forbidden not in code, f"{tf.name} references {forbidden!r} in configuration"


def test_revocation_is_not_gated_in_the_configuration() -> None:
    """FR-006, from the source rather than from a live Vault.

    The live assertion lives in test_revocation_asymmetry; this one catches the case where
    someone adds a revocation path to the controlled list and no enclave is running to
    notice.
    """
    control_groups = INFRA / "control-groups.tf"
    if not control_groups.is_file():
        return
    controlled = control_groups.read_text()
    start = controlled.index("controlled_paths")
    block = controlled[start : controlled.index("]", start)]
    for revocation_shaped in ("revoke", "delete", "suspend"):
        assert revocation_shaped not in block.lower(), (
            f"a revocation-shaped path ({revocation_shaped!r}) entered the controlled list. "
            "Revocation is unilateral and immediate; gating it is the change that makes "
            "people route around the control during an incident."
        )


def test_break_glass_is_not_in_the_controlled_paths() -> None:
    """FR-003a. Root regeneration is gated by the unseal threshold, not by this feature.

    Verified against the CLI: it "generates a new root token by combining a quorum of share
    holders". Control Groups cannot intercept a sys operation of that kind, so listing it
    would be configuration that silently does nothing.
    """
    control_groups = INFRA / "control-groups.tf"
    if not control_groups.is_file():
        return
    text = control_groups.read_text()
    start = text.index("controlled_paths")
    block = text[start : text.index("]", start)]
    assert "generate-root" not in block, (
        "break-glass entered the controlled paths. It cannot be gated here — its strength "
        "comes from the unseal threshold."
    )
