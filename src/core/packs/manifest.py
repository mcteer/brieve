# SPDX-License-Identifier: Apache-2.0
"""What a pack declares. Data only — nothing here is executable.

Every reference to behaviour in this module is a **name**: a tool declaration names a
handler, a hook declaration names a handler, a pack names a probe. Resolution happens at
registration against what the platform already provides, so loading a manifest cannot run
pack code even in principle. That is why `PackManifest` is a frozen dataclass tree and not,
say, a plugin entry point.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from core.hooks.types import CapabilityKind, HookPhase
from core.registry.memory import ProductMode, RiskClass

#: Where a pack's content came from. Not decorative: `adopted` requires `upstream` and
#: promotion verifies the pinned commit; `authored` skips that check and gains an
#: obligation instead — FR-027d's format requirement, so it can become `adopted` later
#: without a rewrite.
Provenance = Literal["adopted", "authored"]

#: How a tool is reached. A tool PROPERTY (Principle II), never a uniformity requirement:
#: MCP where a mature server exists, native otherwise. Authoring an MCP server merely for
#: protocol consistency is explicitly not required.
Transport = Literal["mcp", "native"]


class ManifestError(ValueError):
    """A manifest that cannot be trusted. Carries the reason code the refusal records."""

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class UpstreamPin:
    """Where adopted content came from, and exactly which bytes."""

    repository: str
    commit: str
    licence: str
    retrieved: str


@dataclass(frozen=True)
class SkillPin:
    """An executed artifact, therefore pinned (ADR-0030).

    ``digest`` is what makes "pinned" checkable rather than asserted. A skill whose bytes
    changed without its version changing is exactly the ungated drift Principle VIII exists
    to stop, and it is invisible without a hash.
    """

    name: str
    path: str
    version: str
    digest: str


@dataclass(frozen=True)
class ToolDeclaration:
    """One tool, as the pack declares it.

    Three of these fields exist because the registry *requires* them in practice and a pack
    that omitted them would fail somewhere far from the manifest:

    ``observer`` — the registry calls this "required in practice for a non-repeatable
    tool: without one, an interrupted step resolves to CANNOT_DETERMINE and parks the run."
    Every `write` and `destructive` pack tool is non-repeatable, so without this field every
    interesting pack tool would ship with 005's re-observation unreachable.

    ``product_mode`` / ``product`` — `ToolRegistry.register` raises a bare `ValueError` when
    `product_mode != "none"` without them. A pack should refuse in its own vocabulary at
    load rather than surface a driver error from three layers down.
    """

    name: str
    risk_class: RiskClass
    transport: Transport
    handler: str
    #: Names the observer to resolve, not an observer. See the module docstring.
    observer: str | None = None
    product_mode: ProductMode = "none"
    product: str | None = None
    product_action: str | None = None
    #: False when repeating the call could duplicate an external effect. Declared by the
    #: pack author because only they know, and deliberately not inferred from `risk_class`:
    #: a `read` against a paginating API can be non-repeatable and a `write` idempotent.
    repeatable: bool = True


@dataclass(frozen=True)
class PackHookDeclaration:
    """A hook a pack contributes to the pipeline.

    **Pack hooks are a new enforcement surface, authored outside this repository.** The
    plan says so plainly rather than claiming this feature adds no enforcement point,
    because that claim was wrong. It is bounded two ways, and this record carries the first:
    ``capability_kind`` may never be ``GOVERNANCE``.

    ``has_required_governance_hooks`` identifies the platform's own enforcement by
    ``capability_kind == GOVERNANCE``. A pack able to register at that kind could satisfy
    the platform's enforcement-is-whole check *with its own hook* — enforcement authored by
    whoever ships a pack, which is precisely what Principle III exists to prevent. Refused
    at load, not at review: review is when somebody looked, load is when it matters.

    The second bound is asserted rather than declared: ``GovernanceCapability`` still runs
    first, with pack hooks present.
    """

    name: str
    phase: HookPhase
    capability_kind: CapabilityKind
    handler: str


@dataclass(frozen=True)
class WorkflowDeclaration:
    """A named, tiered composition a definition may or may not be allowed to run.

    ``minimum_tier`` is what a competency tier bounds (ADR-0045). Tiers restrict
    **workflows, never tools** — the ceiling answers about tools, and two mechanisms
    answering one question is the duplication ADR-0044 forbids.
    """

    name: str
    minimum_tier: int
    paved: bool


@dataclass(frozen=True)
class PackManifest:
    """A pack, as declared. Loading verifies it; nothing here executes."""

    name: str
    product: str
    version: str
    provenance: Provenance
    #: Names the probe that answers "is this product reachable". Required whenever any tool
    #: declares a product — see `loader.probe_required` for why its absence is the sharpest
    #: trap in this feature.
    probe: str | None = None
    upstream: UpstreamPin | None = None
    tools: tuple[ToolDeclaration, ...] = ()
    skills: tuple[SkillPin, ...] = ()
    hooks: tuple[PackHookDeclaration, ...] = ()
    workflows: tuple[WorkflowDeclaration, ...] = ()
    eval_suites: tuple[str, ...] = ()
    #: Case counts per suite, as shipped. Checked against the floor at load.
    eval_case_counts: dict[str, int] = field(default_factory=dict)

    @property
    def declares_a_product(self) -> bool:
        """Whether any tool reaches a product, and therefore whether a probe is required."""
        return any(tool.product for tool in self.tools)


__all__ = [
    "ManifestError",
    "PackHookDeclaration",
    "PackManifest",
    "Provenance",
    "SkillPin",
    "ToolDeclaration",
    "Transport",
    "UpstreamPin",
    "WorkflowDeclaration",
]
