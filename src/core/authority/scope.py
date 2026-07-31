# SPDX-License-Identifier: Apache-2.0
"""What a task entails, computed from the tools it asked for (016, ADR-0056).

Principle IV's intersection is `user ∩ agent ceiling ∩ task scope ∩ policy`, and until this
feature the third term had nothing behind it: a run carried its definition's whole ceiling
for its whole duration. This is that term.

**Derived, not declared.** The scope comes from the run's requested tools and the paths their
manifests declare, so nothing new has to be authored per agent definition and nothing can
drift from the tools it describes.

**What this actually narrows today, stated plainly because it is less than it sounds.** Every
tool in the packs that exist reaches the same place — the agent's own secret space, which its
ceiling defines — so the PATH set is identical whichever of them a run requests. What differs
is the CAPABILITY: a run asking only to read receives `read`, and never the `create`/`update`
a write tool would have added. That is real narrowing and it is not path narrowing, and a
reader who expected the latter should know the difference before trusting a claim about it.

The mechanism supports path narrowing and will deliver it the moment a pack ships tools that
reach different places. What is bought in both cases is the *relative* property — a run
requesting a subset of tools receives a subset of authority — which is the difference between
per-definition and per-task.

**Undeclared refuses.** A tool that has not said what it touches cannot be granted anything,
and granting the ceiling instead "to be safe" is how a ceiling becomes decorative. The
loader already refuses to load a `secret_touching` tool without `paths`; this refuses at
launch for anything that slipped through, because fail-closed at two layers costs nothing and
the alternative is an over-grant nobody notices.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from core.packs.manifest import ToolDeclaration


class ScopeUndetermined(ValueError):
    """A requested tool did not declare what it reaches, so no grant can be computed.

    Deliberately an error rather than an empty scope. An empty scope is a valid grant that
    reaches nothing; this is the platform being unable to say, which must refuse the launch
    (FR-004) rather than proceed on a guess in either direction.
    """

    def __init__(self, undetermined: frozenset[str]) -> None:
        names = ", ".join(sorted(undetermined))
        super().__init__(
            f"cannot compute task scope: {names} declared no paths. A grant covering the "
            f"whole ceiling instead would make the ceiling decorative, so the launch refuses."
        )
        self.undetermined = undetermined


@dataclass(frozen=True)
class EntailedScope:
    """The resources a task entails, ready to become a grant's authorization details."""

    #: path → the capabilities the task needs there. A mapping rather than two collections
    #: because Vault's RAR is path→capabilities, and flattening it here would mean
    #: reassembling it at the wire, which is where the two would drift.
    paths: dict[str, frozenset[str]] = field(default_factory=dict)

    #: Tools that declared nothing. Non-empty means the launch refuses.
    undetermined: frozenset[str] = frozenset()

    def require_determined(self) -> None:
        if self.undetermined:
            raise ScopeUndetermined(self.undetermined)

    def as_authorization_details(self) -> list[dict[str, object]]:
        """The RAR array Vault evaluates. `vault:path_access` is Vault's type, not ours."""
        return [
            {
                "type": "vault:path_access",
                "path": path,
                "capabilities": sorted(capabilities),
            }
            for path, capabilities in sorted(self.paths.items())
        ]

    def issubset_of(self, ceiling_paths: dict[str, frozenset[str]]) -> bool:
        """Is every path *and capability* here permitted by the ceiling?

        Capability-aware on purpose: a task entailing `update` on a path the ceiling grants
        only `read` is outside the ceiling, and a path-only comparison would call it inside.
        """
        for path, capabilities in self.paths.items():
            permitted = _ceiling_capabilities(path, ceiling_paths)
            if permitted is None or not capabilities <= permitted:
                return False
        return True


def entailed_scope(
    *,
    requested_tools: frozenset[str],
    tools: dict[str, ToolDeclaration],
    agent_space: frozenset[str],
) -> EntailedScope:
    """Union the declared paths of the tools this run asked for.

    ``agent_space`` is what the definition's ceiling grants — the paths this agent may reach
    at all. A tool declaring ``{agent_space}`` expands to each of them.

    **Why the space comes from the ceiling and not from the definition's name.** The first
    version templated on the agent id, which produced `secret/data/planner-agent/*` where the
    ceiling grants `secret/data/planner/*` — and for `vault-agent`, whose space is
    `secret/data/conformance/*`, nothing name-derived could ever have matched. A convention
    that has to agree with a record is a second source of truth; reading the record is one.

    ``tools`` is the registry's view keyed by tool name. A requested tool absent from it is
    **not** undetermined — it is a tool this run may not use at all, which the ceiling check
    already refuses in its own vocabulary. Treating it as undetermined here would report a
    scope problem for an authorization one and send whoever reads it to the wrong place.
    """
    paths: dict[str, set[str]] = {}
    undetermined: set[str] = set()

    for name in sorted(requested_tools):
        declaration = tools.get(name)
        if declaration is None:
            continue
        if not declaration.paths:
            if declaration.risk_class == "secret_touching":
                undetermined.add(name)
            # A tool that reaches no secret needs no path grant, and saying so is not the
            # same as failing to say anything. `echo` is the case: it touches nothing, so it
            # contributes nothing, and a run of only such tools gets an empty scope — which
            # is a correct grant rather than an error.
            continue
        for grant in declaration.paths:
            for expanded in _expand(grant.path, agent_space):
                paths.setdefault(expanded, set()).update(grant.capabilities)

    return EntailedScope(
        paths={path: frozenset(caps) for path, caps in paths.items()},
        undetermined=frozenset(undetermined),
    )


def _expand(template: str, agent_space: frozenset[str]) -> list[str]:
    """Resolve `{agent_space}` against what the ceiling actually grants.

    A template naming no placeholder is used as written — that is how a tool declares a path
    outside its agent's own space, which the ceiling check then refuses unless the ceiling
    genuinely permits it.
    """
    if "{agent_space}" not in template:
        return [template]
    return sorted(template.replace("{agent_space}", space) for space in agent_space)


def _ceiling_capabilities(
    path: str, ceiling_paths: dict[str, frozenset[str]]
) -> frozenset[str] | None:
    """What the ceiling permits at this path, honouring its `*` suffixes.

    Vault policy globs and RAR exact matches are different languages: the ceiling says
    `secret/data/planner/*` and a grant says `secret/data/planner/greeting`. Comparing them
    as strings would find no match and refuse every legitimate grant, so the prefix is
    resolved here — the one place the two vocabularies meet.
    """
    if path in ceiling_paths:
        return ceiling_paths[path]
    for pattern, capabilities in ceiling_paths.items():
        if pattern.endswith("*") and path.startswith(pattern[:-1]):
            return capabilities
    return None


__all__ = ["EntailedScope", "ScopeUndetermined", "entailed_scope"]
