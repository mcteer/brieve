# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — fail reasons and pins are identity only (049 T015; 051 T019, A14).

051 widened the surface: a phase now receives skill content as well as its own instruction,
and records a key per delivered skill. Both bodies must stay out of the map, out of the
checkpoint payload, and out of a phase failure reason.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.progress import PhaseName, PhaseStatus
from core.packs.manifest import ManifestError
from surfaces.dispatch.entrypoint import (
    AGENT_PINS_KEY,
    _bind_phase_or_fail,
    _payload_with_progress,
)
from surfaces.dispatch.phase_agents import bind_phase_agents
from tests.conformance.phase_agents.fixtures import (
    SkillSpec,
    fake_run,
    run_at,
    write_authoring_pack,
)

BODY_MARKER = "Unique steer for this phase of alpha"

#: A phrase that appears only inside the delivered skill, so finding it in a record is
#: unambiguous evidence that content leaked rather than a coincidence of wording.
SKILL_MARKER = "practice that must never reach the record"
BOUND_SKILL = SkillSpec("house-style", body=f"# fixture skill\n{SKILL_MARKER}\n", phases=("write",))


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


def test_a_delivered_skill_is_recorded_by_name_and_digest_only(tmp_path: Path) -> None:
    """The 051 half of the same property.

    The skill's bytes reach the model. Its record is a name and a hash — and the last
    assertion is what keeps this row honest: the content really was delivered, so the
    absence above is a property of the record rather than of an empty run.
    """
    write_authoring_pack(tmp_path, "alpha", skills=(BOUND_SKILL,))
    run = fake_run(("alpha",), tmp_path)
    loaded = bind_phase_agents(run, PhaseName.WRITE)

    assert SKILL_MARKER not in str(run.agent_content_pins)
    assert SKILL_MARKER not in str(_payload_with_progress({}, run))
    assert BODY_MARKER not in str(run.agent_content_pins)
    assert SKILL_MARKER in loaded.body, "the skill was never delivered; this row proves nothing"


def test_the_delivery_record_carries_digests_not_content(tmp_path: Path) -> None:
    """Every value is a hash. A record holding anything else is holding content."""
    write_authoring_pack(tmp_path, "alpha", skills=(BOUND_SKILL,))
    run = fake_run(("alpha",), tmp_path)
    bind_phase_agents(run, PhaseName.WRITE)

    recorded = _payload_with_progress({}, run)[AGENT_PINS_KEY]
    assert recorded
    for key, value in recorded.items():
        assert len(value) == 64 and all(c in "0123456789abcdef" for c in value), (key, value)
