# SPDX-License-Identifier: Apache-2.0
"""Drive the entrypoint's authoring construction without Nomad (041, T008).

**The rows must be able to build the registry with the branch ON and with it OFF**, in one
process. There is no pre-041 tree to execute — 040's M3 recorded that trap — so "before" has
to be constructible rather than checked out.

This helper deliberately drives `surfaces.dispatch.authoring`, the same module `main()` calls,
rather than reimplementing registration. A harness that registered the tools itself would let
every reachability row pass while the production path stayed unwired, which is the exact defect
041 exists to close and would be an embarrassing way to reintroduce it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.authoring.artifact import AuthoredArtifact
from core.authoring.tool import AuthoringTools
from core.authoring.workspace import Trees
from core.registry.memory import ToolRegistry
from surfaces.dispatch.authoring import (
    ANALYZER,
    PROPOSER,
    authoring_registry_for,
    authoring_role,
)
from surfaces.toolset import build_registry, known_tools


@dataclass(frozen=True)
class BuiltRegistry:
    """A registry as the entrypoint would have built it, plus what a ceiling could then name."""

    registry: ToolRegistry
    vocabulary: frozenset[str]
    trees: Trees | None = None
    artifact: AuthoredArtifact | None = None
    #: The analyzer's handles, so a row can read `consulted` and the artefact afterwards.
    tools: AuthoringTools | None = None


def build_as_entrypoint(
    *,
    role: str | None,
    tmp_path: Path,
    packs: list[str] | None = None,
    authoring_enabled: bool = True,
    proposal_handler: object = None,
    proposal_observer: object = None,
) -> BuiltRegistry:
    """Construct the registry the way `main()` does, for a task of ``role``.

    ``authoring_enabled=False`` is the **rigged-off** construction: everything else identical,
    the authoring branch skipped. It is what A1's "before" and A4's self-test run against, and
    it is why this helper takes the flag rather than the caller monkeypatching the entrypoint.
    """
    registry, _loaded = build_registry(packs=packs or [])
    trees: Trees | None = None
    artifact: AuthoredArtifact | None = None
    tools: AuthoringTools | None = None

    if authoring_enabled and role == ANALYZER:
        subject = tmp_path / "subject"
        subject.mkdir(parents=True, exist_ok=True)
        workspace = tmp_path / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        trees = Trees(subject=subject.resolve(), workspace=workspace.resolve())
        artifact = AuthoredArtifact()
        registration = authoring_registry_for(
            ANALYZER, registry=registry, trees=trees, artifact=artifact
        )
        tools = registration.tools
    elif authoring_enabled and role == PROPOSER:
        authoring_registry_for(
            PROPOSER,
            registry=registry,
            proposal_handler=proposal_handler or (lambda arguments: {"ok": True}),
            proposal_observer=proposal_observer or _NullObserver(),
        )

    return BuiltRegistry(
        registry=registry,
        vocabulary=known_tools(registry),
        trees=trees,
        artifact=artifact,
        tools=tools,
    )


class _NullObserver:
    """An observer that answers nothing, for rows about registration rather than publishing."""

    def observe(self, *_args: object, **_kwargs: object) -> None:
        return None


def role_from(env: dict[str, str]) -> str | None:
    """Re-exported so a row asserts the production reader, not its own copy of the rule."""
    return authoring_role(env)


__all__ = ["BuiltRegistry", "build_as_entrypoint", "role_from"]
