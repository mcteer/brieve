# SPDX-License-Identifier: Apache-2.0
"""Bind exactly one pack's phase instruction at Build phase start (049)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.authoring.progress import PhaseName
from core.packs.agents import PhaseAgents, load_phase_agents
from core.packs.loader import FilesystemPackLoader
from core.packs.manifest import ManifestError
from surfaces.toolset import PACKS_ROOT


def _pack_names(run: Any) -> tuple[str, ...]:
    bound = getattr(run, "bound_packs", None)
    if bound is not None:
        return tuple(str(name) for name in bound if str(name).strip())
    return tuple(part for part in os.environ.get("RUN_PACKS", "").split(",") if part.strip())


def bind_phase_agents(
    run: Any,
    phase: PhaseName | str,
    *,
    loader: FilesystemPackLoader | None = None,
    packs_root: Path | None = None,
) -> PhaseAgents:
    """Load the bound pack's instruction for ``phase``. Size-1 pack set required."""
    names = _pack_names(run)
    if len(names) == 0:
        raise ManifestError("Build is not bound to a pack", reason_code="pack_unbound")
    if len(names) > 1:
        raise ManifestError("Build is bound to more than one pack", reason_code="pack_ambiguous")
    root = packs_root if packs_root is not None else Path(getattr(run, "packs_root", PACKS_ROOT))
    pack_loader = loader or FilesystemPackLoader(root)
    loaded = load_phase_agents(names[0], phase, loader=pack_loader, packs_root=root)
    key = f"{loaded.pack}/agents/{loaded.phase.value}@{loaded.version}"
    pins = dict(getattr(run, "agent_content_pins", {}) or {})
    pins[key] = loaded.digest
    run.agent_content_pins = pins
    run.phase_instruction = loaded.body
    return loaded


__all__ = ["bind_phase_agents"]
