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


@dataclass(frozen=True)
class ToolPathGrant:
    """One path a tool reaches, and what it may do there.

    Shaped like Vault's `vault:path_access` so that a future consumer — a rich authorization
    request, an intake report — can use it without a translation layer. Nothing consumes it
    today; see the field's own note.
    """

    path: str
    capabilities: tuple[str, ...]


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
class UnsatisfiableRecommendation:
    """A step adopted content recommends and **no registry tool can perform** (051, FR-015).

    **"Unsatisfiable" is scoped to the tool registry, not to this repository.** The
    distinction is not pedantic: the eval lane really does run `terraform validate`
    (`tests/evals_live/write_gates.py` shells out to it as gate one of Write scoring). What
    does not exist is a registry tool an authoring agent can call on the branch it is
    proposing — so the run's own artefacts were never formatted or validated by the platform.
    A `recommendation` claiming more than that is false, and the repository disproves it.

    **Declared by the pack, never inferred by a model.** A model's account of its own work is
    not evidence (Principle IX). A declaration is pinned, reviewed, identical on every run,
    and checkable against the registry — which is what lets `load_packs` refuse one that has
    gone stale, and what makes the sentence a reviewer reads derive from the manifest alone.
    """

    #: The registry tool name that *would* satisfy this. If the registry ever offers it, the
    #: declaration has gone stale and loading refuses rather than telling a reviewer to go and
    #: do work the platform already did.
    capability: str
    #: The reviewer-facing sentence, rendered verbatim into the pull request. Never
    #: reformatted, never model-authored.
    recommendation: str


@dataclass(frozen=True)
class SkillPin:
    """An executed artifact, therefore pinned (ADR-0030).

    ``digest`` is what makes "pinned" checkable rather than asserted. A skill whose bytes
    changed without its version changing is exactly the ungated drift Principle VIII exists
    to stop, and it is invisible without a hash.

    051 added *where it applies*. Before it, this record said a skill was adopted and
    governed and nothing more — every pack's `content_pins` named skills no model ever
    received, which read as "this governed the run" and was true of none of them.
    """

    name: str
    path: str
    version: str
    digest: str
    #: WHICH PHASES RECEIVE THIS SKILL. Empty means adopted, pinned, and delivered nowhere —
    #: a legitimate state during staged adoption, and one the run record must keep visible
    #: rather than let it read as delivery. Each entry must be a `PhaseName` value and must
    #: name a phase this pack ships an `[[agents]]` instruction for.
    #:
    #: **Order here is not delivery order.** This filters; `[[skills]]` declaration order
    #: orders, so identical manifest content produces an identical instruction (FR-006).
    phases: tuple[str, ...] = ()
    #: What this skill recommends that no registry tool can carry out.
    unsatisfiable: tuple[UnsatisfiableRecommendation, ...] = ()
    #: THE SKILL DIGEST `unsatisfiable` WAS LAST EXAMINED AGAINST, and it must equal
    #: `digest`.
    #:
    #: Required of **every** skill, including one declaring nothing: "nothing here is
    #: unsatisfiable" is itself a claim, and it goes stale on a bump exactly like a
    #: non-empty one. Without this, an upstream bump that adds a step the platform cannot
    #: perform lands silently — the model correctly declines to perform it, and the pull
    #: request still names only what the old declaration named, telling a reviewer that less
    #: work remains than actually does. That is the overstatement Principle IX forbids,
    #: pointed the other way, and it is invisible at load without a recorded digest to
    #: disagree with.
    unsatisfiable_reviewed_at: str = ""


@dataclass(frozen=True)
class AgentPin:
    """Pinned executed instruction for one Build phase of one pack (049, ADR-0030).

    Parallel to ``SkillPin``: a pin, not the instruction body, and not a skill. ``phase``
    must be a ``PhaseName`` value. ``digest`` is SHA-256 of ``AGENTS.md`` bytes.
    """

    phase: str
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
    #: WHAT THIS TOOL REACHES, and with what capability.
    #:
    #: **Declared for review, not for enforcement.** Nothing at runtime reads this: a run's
    #: authority is the ceiling its definition carries, manufactured per allocation and
    #: short-lived (ADR-0057). What this field buys is that a reviewer — or ADR-0004's intake
    #: gauntlet — can see what a tool touches without reading its handler, and that a pack
    #: author has to think about it before shipping.
    #:
    #: It arrived with 016, which intended to derive per-run scope from it. That feature was
    #: parked when the workload turned out to want breadth rather than narrowness, and the
    #: declaration survived on its own merits: `risk_class` sat here unread for two features
    #: before 013 gave it meaning, and was worth having in the meantime for the same reason.
    #:
    #: `{agent_space}` names the agent's own secret space, resolved against its ceiling. Kept
    #: as a token rather than expanded because expanding it needs a ceiling read, and the
    #: point of this field is to be legible without one.
    paths: tuple[ToolPathGrant, ...] = ()


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
    agents: tuple[AgentPin, ...] = ()
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
    "AgentPin",
    "ManifestError",
    "PackHookDeclaration",
    "PackManifest",
    "Provenance",
    "SkillPin",
    "ToolDeclaration",
    "Transport",
    "UnsatisfiableRecommendation",
    "UpstreamPin",
    "WorkflowDeclaration",
]
