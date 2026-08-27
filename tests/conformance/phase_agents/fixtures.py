# SPDX-License-Identifier: Apache-2.0
"""Fixture authoring packs for 049 rows. Invented pack names, not managed-product IDs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from core.authoring.progress import PHASE_ORDER, PhaseName, advance, initial_progress

PHASES: tuple[str, ...] = tuple(p.value for p in PHASE_ORDER)


def digest_of(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class SkillSpec:
    """One ``[[skills]]`` entry to write, and the single way it may be broken.

    ``phases=None`` omits the key entirely, which is the shape every pack shipped before
    051 and the one FR-011 requires to keep behaving exactly as it did.
    """

    name: str
    body: str = "# fixture skill\nPractice the fixture pack pins.\n"
    path: str = ""
    phases: tuple[str, ...] | None = None
    unsatisfiable: tuple[tuple[str, str], ...] = ()
    #: ``None`` records the file's own digest — the reviewed-and-current case.
    reviewed_at: str | None = None
    drift: bool = False
    empty: bool = False
    absent: bool = False

    def __post_init__(self) -> None:
        if not self.path:
            object.__setattr__(self, "path", f"skills/{self.name}/SKILL.md")


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
    skills: tuple[SkillSpec, ...] = (),
) -> Path:
    """Write a complete (or deliberately broken) authoring pack under ``root / name``.

    ``skills`` writes a ``[[skills]]`` entry per spec, with the file on disk. Each spec can
    be broken one way at a time — drifted bytes, empty bytes, an absent file, a declaration
    reviewed against a stale digest — so a row asserts one refusal rather than several at once.
    """
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
    skill_blocks: list[str] = []
    for spec in skills:
        body = spec.body.encode()
        recorded = digest_of(body)
        if spec.drift:
            (pack / spec.path).parent.mkdir(parents=True, exist_ok=True)
            (pack / spec.path).write_bytes(body + b"\ndrifted after the pin was taken\n")
        elif spec.empty:
            (pack / spec.path).parent.mkdir(parents=True, exist_ok=True)
            (pack / spec.path).write_bytes(b"   \n")
        elif not spec.absent:
            (pack / spec.path).parent.mkdir(parents=True, exist_ok=True)
            (pack / spec.path).write_bytes(body)
        reviewed = spec.reviewed_at if spec.reviewed_at is not None else recorded
        lines = [
            "[[skills]]",
            f'name = "{spec.name}"',
            f'path = "{spec.path}"',
            'version = "0.1.0"',
            f'digest = "{recorded}"',
            f'unsatisfiable_reviewed_at = "{reviewed}"',
        ]
        if spec.phases is not None:
            rendered = ", ".join(f'"{ph}"' for ph in spec.phases)
            lines.append(f"phases = [{rendered}]")
        lines.append("")
        for capability, recommendation in spec.unsatisfiable:
            lines += [
                "[[skills.unsatisfiable]]",
                f'capability = "{capability}"',
                f'recommendation = "{recommendation}"',
                "",
            ]
        skill_blocks.append("\n".join(lines))

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
{"".join(skill_blocks)}
{"".join(agent_blocks)}
""",
        encoding="utf-8",
    )
    if plant_root_agents:
        (pack / "AGENTS.md").write_text("# stand-in root agents\n", encoding="utf-8")
        (root / "AGENTS.md").write_text("# repository-root stand-in\n", encoding="utf-8")
    if plant_skill:
        # An UNDECLARED skill file: on disk, named by no `[[skills]]` entry, and therefore
        # never opened by delivery. `planted` rather than `skills` — the parameter owns that
        # name now, and the two mean different things.
        planted = pack / "skills" / "guide"
        planted.mkdir(parents=True, exist_ok=True)
        (planted / "SKILL.md").write_text("# skill is not a phase instruction\n", encoding="utf-8")
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
