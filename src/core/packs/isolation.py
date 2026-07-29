# SPDX-License-Identifier: Apache-2.0
"""What a definition reaches, and the two things it must never reach.

**A pack cannot widen a ceiling.** This is the most plausible defect in the whole feature,
because a pack that grants reads exactly like the pack system working: tools appear, calls
succeed, nothing looks wrong. A definition reaches only the packs it names, and within them
only the tools its ceiling already permitted — the pack narrows, never widens.

**An ambiguous tool name refuses.** Two packs may declare the same tool name; an unqualified
reference reachable from both is refused rather than resolved by load order, because load
order changes without anybody deciding it did. A name is qualified by its pack.
"""

from __future__ import annotations

from core.authority.bindings import DefinitionBindings
from core.authority.types import AuthorityScope
from core.packs.registration import LoadedPack
from core.packs.workflows import WorkflowRecord


class IsolationRefused(Exception):
    """A definition reached for something its bindings or ceiling do not permit."""

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def reachable_tools(
    bindings: DefinitionBindings,
    loaded: dict[str, LoadedPack],
    ceiling: AuthorityScope,
) -> frozenset[str]:
    """Tools this definition may call: named packs, INTERSECTED with its ceiling.

    The intersection direction is the whole point. A pack contributes candidates; the
    ceiling decides. Reversing it — letting a pack's declarations extend the ceiling —
    would be a pack granting authority, which is the shortcut FR-005 forbids and the one
    that would read as a feature.
    """
    from_packs = {
        name for pack in bindings.packs if pack in loaded for name in loaded[pack].tool_names
    }
    return frozenset(from_packs & ceiling.tool_names)


def assert_pack_does_not_widen(
    bindings: DefinitionBindings,
    loaded: dict[str, LoadedPack],
    ceiling: AuthorityScope,
) -> None:
    """Refuse when a named pack declares a tool the ceiling does not permit.

    Refusing rather than silently intersecting, because the two say different things. A
    silent intersection treats an over-declaring pack as a configuration that happens to be
    narrower than it looks; refusing says the pack and the ceiling disagree about what this
    definition may do, and somebody should decide which is right.
    """
    for pack_name in sorted(bindings.packs):
        pack = loaded.get(pack_name)
        if pack is None:
            raise IsolationRefused(
                f"definition {bindings.agent_definition_id!r} names pack {pack_name!r}, "
                f"which is not loaded",
                reason_code="pack_not_loaded",
            )
        beyond = sorted(set(pack.tool_names) - ceiling.tool_names)
        if beyond:
            raise IsolationRefused(
                f"pack {pack_name!r} declares {beyond} which definition "
                f"{bindings.agent_definition_id!r}'s ceiling does not permit; a pack "
                f"narrows what a definition may do and never widens it",
                reason_code="pack_exceeds_ceiling",
            )


def resolve_tool_name(
    name: str, bindings: DefinitionBindings, loaded: dict[str, LoadedPack]
) -> str:
    """Resolve a possibly-unqualified tool name to `pack/tool`, or refuse ambiguity.

    A qualified name (`vault/read`) always resolves. An unqualified one resolves only if
    exactly one reachable pack declares it — otherwise the caller is asking for something
    that means two different things, and picking one by load order means the answer changes
    when the directory listing does.
    """
    if "/" in name:
        pack_name, _, tool = name.partition("/")
        if pack_name not in bindings.packs:
            raise IsolationRefused(
                f"definition does not name pack {pack_name!r}",
                reason_code="pack_not_reachable",
            )
        return f"{pack_name}/{tool}"

    owners = sorted(
        pack for pack in bindings.packs if pack in loaded and name in loaded[pack].tool_names
    )
    if not owners:
        raise IsolationRefused(
            f"no reachable pack declares tool {name!r}", reason_code="pack_not_loaded"
        )
    if len(owners) > 1:
        raise IsolationRefused(
            f"tool {name!r} is declared by {owners}; qualify it as <pack>/{name}. Resolving "
            f"by load order would make the answer change when the directory listing does",
            reason_code="ambiguous_tool_name",
        )
    return f"{owners[0]}/{name}"


def reachable_workflows(
    bindings: DefinitionBindings, loaded: dict[str, LoadedPack]
) -> dict[str, WorkflowRecord]:
    """Workflows from the definition's packs, tiering not yet applied.

    Tier resolution happens at :func:`core.packs.workflows.resolve_workflow`, so this
    returns candidates rather than permissions — the same shape as `reachable_tools`
    returning what a pack offers before the ceiling decides.
    """
    return {
        workflow.name: WorkflowRecord(
            name=workflow.name,
            minimum_tier=workflow.minimum_tier,
            paved=workflow.paved,
            pack=pack_name,
        )
        for pack_name in sorted(bindings.packs)
        if pack_name in loaded
        for workflow in loaded[pack_name].manifest.workflows
    }


__all__ = [
    "IsolationRefused",
    "assert_pack_does_not_widen",
    "reachable_tools",
    "reachable_workflows",
    "resolve_tool_name",
]
