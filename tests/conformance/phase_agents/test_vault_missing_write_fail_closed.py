# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — Vault omit-Write fails closed (049, T026)."""

from __future__ import annotations

from pathlib import Path

from core.authoring.progress import PhaseName, PhaseStatus
from surfaces.dispatch.entrypoint import _bind_phase_or_fail
from tests.conformance.phase_agents.fixtures import fake_run, run_at, write_authoring_pack


def test_vault_named_fixture_missing_write_fails_closed(tmp_path: Path) -> None:
    """A vault-shaped pack name, missing Write: phase FAILED, Propose stays pending."""
    write_authoring_pack(tmp_path, "vaultish", omit_phase="write")
    run = run_at(fake_run(("vaultish",), tmp_path), PhaseName.WRITE)
    reason = _bind_phase_or_fail(run, PhaseName.WRITE)
    assert reason in {"agents_missing", "agents_incomplete"}
    write_state = next(p for p in run.propose_progress.phases if p.name is PhaseName.WRITE)
    assert write_state.status is PhaseStatus.FAILED
    propose = next(p for p in run.propose_progress.phases if p.name is PhaseName.PROPOSE)
    assert propose.status is PhaseStatus.PENDING
