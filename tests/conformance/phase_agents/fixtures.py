# SPDX-License-Identifier: Apache-2.0
"""Fixture authoring packs for 049 rows. Invented pack names, not managed-product IDs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from core.authoring.progress import PHASE_ORDER, PhaseName, advance, initial_progress

PHASES: tuple[str, ...] = tuple(p.value for p in PHASE_ORDER)


def digest_of(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def write_authoring_pack(
    root: Path,
    name: str = "alpha",
    *,
    omit_phase: str | None = None,
    empty_phase: str | None = None,
    wrong_digest_phase: str | None = None,
    skip_provenance: str | None = None,
    plant_root_agents: bool = False,
    plant_skill: bool = False,
    plant_candidate: bool = False,
    extra_workflow: bool = True,
) -> Path:
    """Write a complete (or deliberately broken) authoring pack under ``root / name``."""
    pack = root / name
    pack.mkdir(parents=True, exist_ok=True)
    agent_blocks: list[str] = []
    for phase in PHASES:
        if omit_phase == phase:
            continue
        dest = pack / "agents" / phase
        dest.mkdir(parents=True, exist_ok=True)
        body = f"# {name} {phase}\nUnique steer for this phase of {name}.\n".encode()
        if empty_phase == phase:
            body = b"   \n"
        (dest / "AGENTS.md").write_bytes(body)
        if skip_provenance != phase:
            (dest / "PROVENANCE.md").write_text(
                f"sources: fixture\nauthorship: 2026-08-19\nphase: {phase}\n",
                encoding="utf-8",
            )
        recorded = digest_of(body)
        if wrong_digest_phase == phase:
            recorded = digest_of(b"not the bytes")
        agent_blocks.append(
            "\n".join(
                [
                    "[[agents]]",
                    f'phase = "{phase}"',
                    f'path = "agents/{phase}/AGENTS.md"',
                    'version = "0.1.0"',
                    f'digest = "{recorded}"',
                    "",
                ]
            )
        )
    workflow = ""
    if extra_workflow:
        workflow = """
[[workflows]]
name = "author-widget"
minimum_tier = 2
paved = false
"""
    (pack / "pack.toml").write_text(
        f"""
[pack]
name = "{name}"
product = "{name}"
version = "0.1.0"
provenance = "authored"
probe = "{name}_probe"

[[tools]]
name = "read"
risk_class = "read"
transport = "native"
handler = "h"
product = "{name}"
{workflow}
{"".join(agent_blocks)}
""",
        encoding="utf-8",
    )
    if plant_root_agents:
        (pack / "AGENTS.md").write_text("# stand-in root agents\n", encoding="utf-8")
        (root / "AGENTS.md").write_text("# repository-root stand-in\n", encoding="utf-8")
    if plant_skill:
        skills = pack / "skills" / "guide"
        skills.mkdir(parents=True, exist_ok=True)
        (skills / "SKILL.md").write_text("# skill is not a phase instruction\n", encoding="utf-8")
    if plant_candidate:
        cand = root / "evals" / "prompt-tune" / "candidates" / name / "write"
        cand.mkdir(parents=True, exist_ok=True)
        (cand / "AGENTS.md").write_text("# unpromoted candidate\n", encoding="utf-8")
    return pack


def fake_run(packs: tuple[str, ...], packs_root: Path) -> Any:
    run = SimpleNamespace()
    run.bound_packs = packs
    run.packs_root = packs_root
    run.agent_content_pins = {}
    run.phase_instruction = ""
    run.propose_progress = initial_progress()
    return run


def run_at(run: Any, phase: PhaseName) -> Any:
    run.propose_progress = advance(initial_progress(), into=phase)
    return run
