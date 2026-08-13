# SPDX-License-Identifier: Apache-2.0
"""Deployment-configured repositories a requester may Propose into (047)."""

from __future__ import annotations

import os


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


def packs_declaring_authoring() -> frozenset[str]:
    """Packs whose pack.toml declares an authoring workflow — terraform for 047."""
    return frozenset({"terraform"})


__all__ = ["owned_repositories_from_env", "packs_declaring_authoring"]
