# SPDX-License-Identifier: Apache-2.0
"""Enforcement, in the pipeline (038, FR-014, FR-020; research R23).

**Two `GOVERNANCE`-kind registrations, and their existence is the finding.** The first two
drafts of this feature put the provenance refusal in a module function and the injection lens
"on the analysis path" — both reachable only by a caller remembering to call them. That reads
identically to enforcement in a task list and is not enforcement: Principle III requires every
tool invocation to pass pre- and post-execution hooks in an in-process, fail-closed pipeline,
and `engine.py` orders `GOVERNANCE` first for exactly that reason.

A conformance row over a module function would have been green.

**The lens attaches to `read_subject`, which is why that tool exists.** A read-only mount read
by ordinary file access offers no hook, so ADR-0038's *"injection-lens hooks"* had nowhere to
live. Routing subject reads through a registered tool gives the lens a POST phase to occupy —
and gives FR-014 a place to record an attempt, FR-005b countable reads to truncate, and FR-004
an enumerable "what was consulted".

**The lens records and does not refuse.** Content addressed to the agent is *data*; refusing to
read a file because it contains instructions would let a subject make itself unanalysable, which
hands any repository a way to opt out of inspection by insulting the inspector.
"""

from __future__ import annotations

from typing import Any

from core.audit.schema import AuditEventType
from core.authoring.provenance import ProvenanceLedger
from core.authoring.workspace import digest_of
from core.evals.injection_patterns import INJECTION_PATTERNS
from core.hooks.types import CapabilityKind, HookContext, HookDecision, HookPhase, HookRegistration

#: Which tools enact is **supplied by the caller, never named here.** `core` knows the shape of
#: the rule — do not apply your own output — and assembly knows which registered tools apply
#: configuration to the world. Naming one in this module would put product knowledge in the
#: layer that is supposed to be able to govern anything, which is Principle I at the content
#: layer and is what `test_core_is_product_blind` caught on this hook's first run.
#:
#: Not inferred from `risk_class` either: `destructive` and `enacts` are different questions —
#: a tool that deletes a scratch workspace is destructive and enacts nothing.

#: What the enactment hook reads a digest out of. A tool that enacts content names it here;
#: one that does not is not this hook's business.
_CONTENT_ARGUMENTS = ("content_digest", "plan_digest", "artifact_digest")


def provenance_hook(
    ledger: ProvenanceLedger, *, enacting_tools: frozenset[str]
) -> HookRegistration:
    """PRE: refuse enactment of platform-authored content with no recorded human merge.

    Registered at `GOVERNANCE` kind so it runs first among co-resident capabilities — the
    ordering Principle III requires, and the reason this is a registration rather than a call.
    """

    def handler(ctx: HookContext) -> HookDecision:
        if ctx.tool_name not in enacting_tools:
            return HookDecision(outcome="allow")
        digest = _digest_from(ctx.arguments)
        if digest is None:
            return HookDecision(outcome="allow")
        permitted, provenance = ledger.may_enact(digest)
        if permitted:
            return HookDecision(outcome="allow")
        assert provenance is not None  # narrowed: `may_enact` returns False only with one
        _record_enactment_refusal(ctx, provenance.authoring_correlation_id, digest)
        return HookDecision(
            outcome="deny",
            reason_code="enactment_of_own_output",
            message=(
                f"this content was authored by run {provenance.authoring_correlation_id} and no "
                f"human merge is recorded. Applying is not forbidden; applying one's own output "
                f"is. Merge the proposal and the artefact becomes reviewed configuration."
            ),
        )

    return HookRegistration(
        name="authoring_provenance",
        phase=HookPhase.PRE,
        capability_kind=CapabilityKind.GOVERNANCE,
        handler=handler,
    )


def injection_lens_hook() -> HookRegistration:
    """POST on `read_subject`: record an attempt to instruct the agent, and allow the read.

    **Records `pattern_name` and location; explicitly DROPS the excerpt.** `InjectionFinding`
    carries one, so reusing `injection_patterns` verbatim would make copying analysed private
    code into an append-only store the *natural* implementation — the exact inverse of
    `CANARY_CONTACT`'s rule. The sink's payload gate enforces the same thing; both, because a
    rule held in one place holds until somebody writes a second call site.
    """

    def handler(ctx: HookContext) -> HookDecision:
        if ctx.tool_name != "read_subject":
            return HookDecision(outcome="allow")
        content = str(ctx.arguments.get("_result", "") or "")
        fired = [p.name for p in INJECTION_PATTERNS if p.pattern.search(content)]
        if fired and ctx.run is not None:
            ctx.run.audit_sink.append_event(
                correlation_id=ctx.correlation_id,
                tenant_id=ctx.run.tenant_id,
                event_type=AuditEventType.CONTAINMENT_REFUSED,
                payload={
                    "code": "instruction_addressed_to_agent",
                    "location": str(ctx.arguments.get("path", "")),
                    "digest": digest_of(content),
                    "patterns": sorted(fired),
                },
            )
        # Allowed regardless. See the module docstring: refusing the read would let a subject
        # make itself unanalysable.
        return HookDecision(outcome="allow")

    return HookRegistration(
        name="authoring_injection_lens",
        phase=HookPhase.POST,
        capability_kind=CapabilityKind.GOVERNANCE,
        handler=handler,
    )


def _digest_from(arguments: Any) -> str | None:
    for name in _CONTENT_ARGUMENTS:
        value = arguments.get(name)
        if value:
            return str(value)
    return None


def _record_enactment_refusal(ctx: HookContext, authoring_correlation_id: str, digest: str) -> None:
    if ctx.run is None:  # pragma: no cover - governance hooks always carry the run
        return
    ctx.run.audit_sink.append_event(
        correlation_id=ctx.correlation_id,
        tenant_id=ctx.run.tenant_id,
        event_type=AuditEventType.ENACTMENT_REFUSED,
        payload={
            "content_digest": digest,
            "authoring_correlation_id": authoring_correlation_id,
            "attempted_tool": ctx.tool_name,
        },
    )


__all__ = ["injection_lens_hook", "provenance_hook"]
