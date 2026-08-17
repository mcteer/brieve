# SPDX-License-Identifier: Apache-2.0
"""Deployment-configured repositories a requester may Propose into (047)."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

#: Packs live next to `src/`, never inside it.
_PACKS_ROOT = Path(__file__).resolve().parents[3] / "packs"


def owned_repositories_from_env(
    *,
    environ: dict[str, str] | None = None,
) -> frozenset[str]:
    """Comma-separated ``owner/repo`` list from ``PROPOSE_OWNED_REPOSITORIES``.

    Empty means nobody may propose — fail closed rather than defaulting to the world.
    """
    env = environ if environ is not None else dict(os.environ)
    raw = env.get("PROPOSE_OWNED_REPOSITORIES", "").strip()
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def packs_declaring_authoring(*, packs_root: Path | None = None) -> frozenset[str]:
    """Pack names whose manifest declares a workflow with ``author`` in the name.

    Names come from pack.toml, not from this module: a hardcoded product here would be
    the core learning which packs exist (Principle I). A pack that cannot be read is
    omitted — fail closed for that pack rather than guessing it authors.
    """
    root = packs_root if packs_root is not None else _PACKS_ROOT
    if not root.is_dir():
        return frozenset()
    declared: set[str] = set()
    for pack_dir in root.iterdir():
        manifest_path = pack_dir / "pack.toml"
        if not manifest_path.is_file():
            continue
        try:
            data = tomllib.loads(manifest_path.read_text())
        except tomllib.TOMLDecodeError:
            continue
        pack = data.get("pack")
        if not isinstance(pack, dict):
            continue
        name = str(pack.get("name", "")).strip()
        workflows = data.get("workflows")
        if not name or not isinstance(workflows, list):
            continue
        if any(
            isinstance(entry, dict) and "author" in str(entry.get("name", ""))
            for entry in workflows
        ):
            declared.add(name)
    return frozenset(declared)


__all__ = ["owned_repositories_from_env", "packs_declaring_authoring"]
