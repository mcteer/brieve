# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — phase-fail reasons and pins are identity only (049, T015)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.progress import PhaseName, PhaseStatus
from core.packs.manifest import ManifestError
from surfaces.dispatch.entrypoint import _bind_phase_or_fail
from surfaces.dispatch.phase_agents import bind_phase_agents
from tests.conformance.phase_agents.fixtures import fake_run, run_at, write_authoring_pack

BODY_MARKER = "Unique steer for this phase of alpha"


def test_fail_reason_is_the_code_not_the_body(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", empty_phase="write")
    run = run_at(fake_run(("alpha",), tmp_path), PhaseName.WRITE)
    reason = _bind_phase_or_fail(run, PhaseName.WRITE)
    assert reason == "agents_empty"
    write_state = next(p for p in run.propose_progress.phases if p.name is PhaseName.WRITE)
    assert write_state.status is PhaseStatus.FAILED
    assert write_state.reason == "agents_empty"
    blob = str(run.propose_progress.to_payload())
    assert BODY_MARKER not in blob


def test_successful_pins_are_identity_version_digest(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha")
    run = fake_run(("alpha",), tmp_path)
    loaded = bind_phase_agents(run, PhaseName.RESEARCH)
    key = f"alpha/agents/research@{loaded.version}"
    assert run.agent_content_pins == {key: loaded.digest}
    assert BODY_MARKER not in key
    assert BODY_MARKER not in str(run.agent_content_pins)
    assert BODY_MARKER in loaded.body


def test_manifest_error_does_not_embed_the_instruction_body(tmp_path: Path) -> None:
    write_authoring_pack(tmp_path, "alpha", omit_phase="write")
    from core.packs.loader import FilesystemPackLoader

    with pytest.raises(ManifestError) as caught:
        FilesystemPackLoader(tmp_path).load("alpha")
    assert caught.value.reason_code == "agents_incomplete"
    assert BODY_MARKER not in str(caught.value)
