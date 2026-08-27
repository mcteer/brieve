# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — what a phase was actually given reaches the record (051, T017/T018, row A13).

`RUN_START`'s `content_pins` is written before any phase executes, so it can say what a pack
binds and never what a run was steered by. This map accumulates at each bind, which is what
lets the two be told apart.

**049 set this map and nothing ever wrote it.** `bind_phase_agents` has populated
`run.agent_content_pins` since then, and no checkpoint, audit event, or result body carried
it — per-phase pins existed in memory and nowhere else. The rows below are the first that
could have noticed.

The negative case is the one that matters most. A run that stopped before Write must not be
readable as one whose Write model saw the skill, and a record that only ever adds keys cannot
make that distinction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.authoring.progress import PhaseName
from surfaces.dispatch.entrypoint import AGENT_PINS_KEY, _payload_with_progress
from surfaces.dispatch.phase_agents import bind_phase_agents
from tests.conformance.phase_agents.fixtures import SkillSpec, fake_run, write_authoring_pack


def _pack(root: Path) -> None:
    write_authoring_pack(
        root, "alpha", skills=(SkillSpec("house-style", phases=("write", "judge")),)
    )


def _payload(run: Any) -> dict[str, Any]:
    return _payload_with_progress({}, run)


def test_a_bound_phase_records_the_instruction_it_received(tmp_path: Path) -> None:
    _pack(tmp_path)
    run = fake_run(("alpha",), tmp_path)
    bind_phase_agents(run, PhaseName.WRITE)

    recorded = _payload(run)[AGENT_PINS_KEY]
    assert "alpha/agents/write@0.1.0" in recorded


def test_the_record_reaches_the_checkpoint_payload(tmp_path: Path) -> None:
    """The 049 gap. Held in memory, the map answers nobody."""
    _pack(tmp_path)
    run = fake_run(("alpha",), tmp_path)
    bind_phase_agents(run, PhaseName.RESEARCH)
    assert AGENT_PINS_KEY in _payload(run)


def test_a_run_that_stopped_before_write_records_no_write_delivery(tmp_path: Path) -> None:
    """US2 acceptance 2 — the half that makes the record honest.

    Research bound; Write never did. The skill is bound to Write in the manifest, and the
    record must still not claim Write received anything.
    """
    _pack(tmp_path)
    run = fake_run(("alpha",), tmp_path)
    bind_phase_agents(run, PhaseName.RESEARCH)

    recorded = _payload(run)[AGENT_PINS_KEY]
    assert not [key for key in recorded if "/agents/write@" in key], recorded


def test_reaching_write_is_what_adds_the_write_key(tmp_path: Path) -> None:
    """Without this the negative row above could pass against a record that adds nothing."""
    _pack(tmp_path)
    run = fake_run(("alpha",), tmp_path)

    bind_phase_agents(run, PhaseName.RESEARCH)
    before = set(_payload(run)[AGENT_PINS_KEY])
    bind_phase_agents(run, PhaseName.WRITE)
    after = set(_payload(run)[AGENT_PINS_KEY])

    assert after - before, "binding Write added nothing to the record"
    assert any("/agents/write@" in key for key in after - before)


def test_the_record_is_ordered_so_two_identical_runs_agree(tmp_path: Path) -> None:
    """Sorted, for the same reason `RUN_START` sorts: a diff between trails is a difference."""
    _pack(tmp_path)
    run = fake_run(("alpha",), tmp_path)
    for phase in (PhaseName.WRITE, PhaseName.RESEARCH, PhaseName.JUDGE):
        bind_phase_agents(run, phase)
    recorded = _payload(run)[AGENT_PINS_KEY]
    assert list(recorded) == sorted(recorded)


def test_an_empty_record_writes_no_key(tmp_path: Path) -> None:
    """A run that bound nothing carries no delivery claim at all — not an empty one."""
    _pack(tmp_path)
    run = fake_run(("alpha",), tmp_path)
    assert AGENT_PINS_KEY not in _payload(run)
