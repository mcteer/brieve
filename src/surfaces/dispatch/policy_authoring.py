# SPDX-License-Identifier: Apache-2.0
"""Vault policy authoring's product-aware half (042).

**Everything Vault-specific about this feature lives here or in `surfaces.handlers`.** 041's
authoring tier is product-blind on purpose — a Terraform module and a Vault policy are
written identically — and `test_core_is_product_blind` refuses otherwise. It caught 041 doing
exactly this, which is why the boundary is worth naming rather than assuming.

**The central refusal, three independent layers.** The enclave's Vault holds the policies that
bound the agents running in it, so this is the first feature that could be asked — by a
prompt, by a mistake, or by an instruction planted in a subject — to author the records that
bound the run doing the authoring. Principle IV is unambiguous, and a rule the model is asked
to follow is not a structure:

1. **request validation**, here — a protected `target_policy` refuses before anything is read
2. **a GOVERNANCE pre-hook**, here — the model tried anyway; the act refuses and is recorded
3. **Vault's own ACL**, in `infra/modules/trust-fabric/scratch.tf` — nothing outside
   `scratch-agent-*` is writable at all, which is the only layer that survives a platform bug

Layer 2 is the one V3 deletes to prove the safety case can lose.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.authoring.request import AuthoringRequest, RequestRefused
from core.hooks.types import CapabilityKind, HookContext, HookDecision, HookPhase, HookRegistration

#: Where the trust fabric publishes what it declares. Read-only to runs by policy, on the
#: same mount and the same posture as ceilings and the matrix.
PROTECTED_POLICIES_PATH = "harness-authority/data/protected-policies"

#: The reserved measurement namespace (FR-020). Named here and in `scratch.tf`, and a unit
#: row asserts no trust-fabric policy occupies it.
SCRATCH_PREFIX = "scratch-agent-"

SUPPORTED_SCHEMA_VERSION = 1


class ProtectedSetUnavailable(RequestRefused):
    """The protected set could not be read, so nothing may be authored.

    **Its own type because the response is its own.** An unreadable fabric is an outage; a
    policy that is in the set is a governance decision. Collapsing them would send an
    operator to argue with the protected list during an incident.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, reason_code="protected_set_unavailable")


@dataclass(frozen=True)
class ProtectedSet:
    """The trust-fabric policies no authoring run may touch."""

    names: frozenset[str]
    #: Which record refused, so the trail names the list rather than leaving it to be found.
    source: str = PROTECTED_POLICIES_PATH

    def protects(self, policy_name: str) -> bool:
        """Whether ``policy_name`` is out of bounds, on an exact match.

        **Exact, not prefix.** A prefix rule would make `agent-ceiling-demo` protected
        because `agent-ceiling` is, which quietly forbids authoring for anything whose name
        starts like a platform record — the over-refusal that makes a safety case look
        strong while making the feature unusable.
        """
        return policy_name.strip() in self.names

    def is_scratch(self, policy_name: str) -> bool:
        """Whether the name belongs to the measurement namespace, which nobody may request."""
        return policy_name.strip().startswith(SCRATCH_PREFIX)


def read_protected_set(read_versioned: Any) -> ProtectedSet:
    """Read the published set, or refuse (FR-006, V5).

    **Fail-closed, and the distinction is the point.** An absent record and an unreachable
    fabric both arrive here as "no names", and treating either as an empty set would mean a
    run authoring `agent-ceiling` during a Vault outage — with every row in this feature
    still green, because they all supply a set. `MatrixSource` already draws exactly this
    line for the same reason; this is that reasoning one record over.

    An empty published list is also refused. The trust fabric declares its own policies, so a
    set with nothing in it means the record was written by something that is not that module.
    """
    try:
        record = read_versioned(PROTECTED_POLICIES_PATH)
    except Exception as exc:  # noqa: BLE001 — any read fault is a read fault
        raise ProtectedSetUnavailable(
            f"the protected-policy set could not be read from {PROTECTED_POLICIES_PATH!r}: "
            f"{type(exc).__name__}. Nothing is authored against an unknown protected set — "
            f"an outage that read as 'nothing is protected' would permit exactly the write "
            f"this feature exists to prevent"
        ) from exc

    if record is None:
        raise ProtectedSetUnavailable(
            f"no protected-policy record at {PROTECTED_POLICIES_PATH!r}; the trust fabric "
            f"publishes it with the policies it declares, so its absence means the apply is "
            f"incomplete rather than that nothing needs protecting"
        )

    data = record.get("data", record) if isinstance(record, Mapping) else {}
    inner = data.get("data", data) if isinstance(data, Mapping) else {}
    version = inner.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise ProtectedSetUnavailable(
            f"protected-policy record carries schema_version {version!r}, not "
            f"{SUPPORTED_SCHEMA_VERSION}; guessing at a record this decides authority from "
            f"is how a set gets misread"
        )

    names = frozenset(str(name).strip() for name in inner.get("names") or () if str(name).strip())
    if not names:
        raise ProtectedSetUnavailable(
            "the protected-policy record names nothing. The trust fabric declares its own "
            "policies and publishes them together, so an empty set means the record was "
            "written by something other than that module"
        )
    return ProtectedSet(names=names)


@dataclass(frozen=True)
class PolicyAuthoringRequest:
    """041's request plus the policy it is about (FR-004).

    **Composition rather than inheritance**, so `AuthoringRequest.validate` runs exactly as
    041 wrote it and this adds a check rather than replacing a set of them. FR-014 says the
    tier is consumed unchanged, and a subclass overriding `validate` is the easiest way to
    break that without touching a line of 041's code.
    """

    authoring: AuthoringRequest
    target_policy: str

    def validate(
        self,
        *,
        run_tenant_id: str,
        owned_repositories: frozenset[str],
        packs_declaring_authoring: frozenset[str],
        protected: ProtectedSet,
    ) -> None:
        """Refuse before anything is read, or return (V1).

        **Layer 1 of three.** This is the cheapest refusal and the least trustworthy: it
        binds on the policy the request NAMES, and a run that changed its mind mid-flight
        would sail past it. That is what the hook is for. Both exist because a refusal that
        arrives after a subject has been cloned and read has already done the work it was
        supposed to prevent — 041's request module makes the same argument about producing
        files.
        """
        self.authoring.validate(
            run_tenant_id=run_tenant_id,
            owned_repositories=owned_repositories,
            packs_declaring_authoring=packs_declaring_authoring,
        )

        target = self.target_policy.strip()
        if not target:
            raise RequestRefused(
                "a policy-authoring request names no target policy; what is being changed "
                "is not something to infer from the task text",
                reason_code="target_policy_required",
            )
        if protected.is_scratch(target):
            raise RequestRefused(
                f"{target!r} is in the measurement namespace {SCRATCH_PREFIX!r}, which "
                f"belongs to the impact check. A request naming one is either confused or "
                f"trying to have a throwaway policy published as a real one",
                reason_code="scratch_name_forged",
            )
        if protected.protects(target):
            raise RequestRefused(
                f"{target!r} is a trust-fabric policy: it is part of what bounds the agents "
                f"in this estate, including the one that would be authoring it. Agents are "
                f"structurally excluded from managing their own platform (Principle IV), and "
                f"this refusal arrives before anything is read or authored",
                reason_code="policy_protected",
            )


#: Arguments a tool may carry a policy name in. Checked as a set rather than per tool, so a
#: tool added later with a differently-named argument is covered the moment it uses one of
#: these — and a tool inventing a third spelling is the failure this cannot see, which is why
#: Vault's ACL is the layer underneath.
_POLICY_ARGUMENTS = ("policy_name", "target_policy", "name")

#: Arguments through which a call claims WHICH RUN it is. Checked on every tool rather than
#: only the policy-writing ones, because this is an identity claim rather than a policy name:
#: no tool has a legitimate reason to act as a run other than the one making the call.
#:
#: **042 refused a `scratch_name` argument as "a caller choosing what to overwrite"
#: (`handlers.py`) and then derived that name from `run_id`, which is an argument.** The
#: refusal was right and the route around it was open — a call naming another run's id reaches
#: that run's measurement workspace, and the wildcard grant in `scratch.tf` permits acting on
#: it. Demonstrated against the live enclave, issue #226.
_IDENTITY_ARGUMENTS = ("run_id",)

#: Which tools this hook inspects. Supplied as a constant rather than checked against every
#: tool, because a hook that examined `read_subject`'s file contents for policy names would
#: refuse a run for analysing a repository that mentions `agent-ceiling` in a comment.
POLICY_WRITING_TOOLS = frozenset({"author_file", "vault_policy_impact"})


def _refuse_a_foreign_run(ctx: HookContext) -> HookDecision | None:
    """Deny a call claiming a run id that is not the caller's. `None` when there is nothing to
    refuse (issue #226).

    **Fail-closed when identity cannot be established.** A governance hook always receives its
    run, so an absent one is a misconfiguration — and allowing on absence would make this guard
    removable by arranging for the run to be missing rather than by deleting the check.

    **Compared against the run's own id and nothing else.** There is no list to be on: the only
    run a call may act as is the one making it.
    """
    claimed = ""
    for argument in _IDENTITY_ARGUMENTS:
        claimed = str(ctx.arguments.get(argument, "") or "").strip()
        if claimed:
            break
    if not claimed:
        return None

    run = ctx.run
    actual = str(getattr(run, "run_id", "") or "").strip() if run is not None else ""
    if not actual:
        actual = str(ctx.correlation_id or "").strip()

    if not actual:
        return HookDecision(
            outcome="deny",
            reason_code="run_identity_unavailable",
            message=(
                "a call claims a run id but the pipeline could not establish which run is "
                "making it, so the claim cannot be checked. Refused rather than trusted."
            ),
        )
    if claimed == actual:
        return None
    return HookDecision(
        outcome="deny",
        reason_code="run_id_forged",
        message=(
            f"this call claims to be run {claimed!r} while it is run {actual!r}. A run id is "
            f"not a caller's to choose: the measurement namespace is derived from it, so "
            f"naming another run reaches that run's workspace."
        ),
    )


def protected_policy_hook(protected: ProtectedSet) -> HookRegistration:
    """PRE at GOVERNANCE: refuse a tool call that names a policy the platform runs on (V2).

    **Layer 2 of three, and the one V3 deletes.** Request validation binds on what a request
    NAMED; this binds on what a call actually CARRIES, which is the difference between a run
    that asked wrongly and a run that changed its mind. `SC-003` asserts that removing this
    registration makes a row fail — a safety case that cannot lose is not one.

    **A registration rather than a call**, on 038's finding in this same estate: its first two
    drafts put the provenance refusal in a module function reachable only by a caller
    remembering to call it, which reads identically to enforcement in a task list and is not
    enforcement. `GOVERNANCE` kind runs first among co-resident capabilities, which is the
    ordering Principle III requires.

    **The attempt is recorded by the engine, not by this handler.** Every PRE decision is
    appended with its hook name, outcome and reason code before the deny propagates — so
    FR-005's "such an attempt MUST be recorded" is the pipeline's property, and a handler
    writing its own event would file the same refusal twice. The row asserts the engine's
    record rather than a second one.

    **Fail-closed is also the engine's**: a handler that raises is caught and turned into a
    deny with `internal_error`. This one raises nothing on purpose, and the row drives a
    deliberately broken variant to assert the pipeline denies rather than allows.
    """

    def handler(ctx: HookContext) -> HookDecision:
        forged = _refuse_a_foreign_run(ctx)
        if forged is not None:
            return forged

        if ctx.tool_name not in POLICY_WRITING_TOOLS:
            return HookDecision(outcome="allow")

        for argument in _POLICY_ARGUMENTS:
            named = str(ctx.arguments.get(argument, "") or "").strip()
            if not named:
                continue
            if protected.is_scratch(named):
                return HookDecision(
                    outcome="deny",
                    reason_code="scratch_name_forged",
                    message=(
                        f"{named!r} is in the measurement namespace, which the impact check "
                        f"derives from the run id and no caller supplies. A call naming one "
                        f"is asking for a throwaway policy to be treated as a real one."
                    ),
                )
            if protected.protects(named):
                return HookDecision(
                    outcome="deny",
                    reason_code="policy_protected",
                    message=(
                        f"{named!r} is a trust-fabric policy — part of what bounds the agent "
                        f"making this call. Agents are structurally excluded from managing "
                        f"their own platform (Principle IV). Refused at the pipeline, so it "
                        f"holds whether or not the request that started this run named it."
                    ),
                )
        return HookDecision(outcome="allow")

    return HookRegistration(
        name="policy_protected",
        phase=HookPhase.PRE,
        capability_kind=CapabilityKind.GOVERNANCE,
        handler=handler,
    )


#: What a citation must resolve against. The pinned Vault operating guides are already the
#: answering surface's ground (ADR-0004), so a proposal's reasoning rests on the same corpus a
#: person would be shown if they asked the question directly.
#: What counts as a citation in a rationale's free text.
#:
#: **045 added the `/endorsed/` alternative, and until it did the authoring half of this feature
#: was a no-op** — customer material was resolvable and never extracted, so a proposal citing an
#: organisation's own standard would have carried the "cites no pinned guidance" disclosure
#: while citing exactly what it was asked to follow. Found by a row that asserted the
#: disclosure rather than the extraction.
#:
#: The two alternatives are enumerated rather than generalised to "any absolute path": a
#: pattern matching every slash-prefixed token would pull file paths and policy names out of a
#: rationale and present them to a reviewer as evidence.
CITATION_PATTERN = re.compile(r"(?:/validated-(?:designs|patterns)|/endorsed)/[\w./-]+(?:#[\w-]+)?")

#: FR-012's disclosure. Appended to the proposal's own disclosures rather than blocking the
#: publish: declining to CLAIM grounding is honest, and refusing to propose at all would make
#: the platform useless for any change the corpus does not happen to discuss.
UNSUPPORTED_DISCLOSURE = (
    "The rationale cites no pinned guidance that resolves. Treat its reasoning as the "
    "proposing agent's own, not as grounded in the validated designs."
)


def render_impact_evidence(impact: Mapping[str, Any]) -> list[str]:
    """Vault's answer, transcribed — never summarised, never interpreted (FR-009, FR-011).

    **The platform writes this, not the model** (Principle IX). Every line is arithmetic over
    what `sys/capabilities` returned: what a token under the current policy could do, what one
    under the proposed policy could do, and the difference. A model asked to describe its own
    change would produce something more readable and less checkable.

    Lines rather than a table because `Proposal.render` emits bullets, and a second rendering
    convention inside one body is how a document stops being scannable.
    """
    lines: list[str] = [f"Measured against the real product by `{impact.get('measured_by', '?')}`."]
    for entry in impact.get("results", ()):
        path = entry.get("path", "?")
        if entry.get("unanswered"):
            lines.append(
                f"`{path}` — **not answered** by the capability check; this path's effect is "
                f"unmeasured and must not be read as unchanged"
            )
            continue
        granted, revoked = entry.get("granted") or [], entry.get("revoked") or []
        if not granted and not revoked:
            held = ", ".join(entry.get("proposed") or []) or "no capabilities"
            lines.append(f"`{path}` — unchanged ({held})")
            continue
        parts = []
        if granted:
            parts.append(f"**grants** {', '.join(granted)}")
        if revoked:
            parts.append(f"**revokes** {', '.join(revoked)}")
        lines.append(f"`{path}` — {'; '.join(parts)}")
    if impact.get("truncated"):
        lines.append(
            "**Truncated**: more paths were declared than the check queries. The unlisted "
            "paths are unmeasured, not unchanged."
        )
    return lines


def resolved_citations(rationale: str, resolves: Any) -> tuple[list[str], bool]:
    """Which cited documents exist in the pin, and whether ANY did (FR-011, FR-012).

    ``resolves`` is supplied rather than imported so this stays testable without the corpus on
    disk and so the caller decides which pin is authoritative — the same seam `answer_question`
    uses for exactly the same reason.
    """
    found: list[str] = []
    for citation in CITATION_PATTERN.findall(rationale or ""):
        path, _, anchor = citation.partition("#")
        if resolves(path, anchor) and citation not in found:
            found.append(citation)
    return found, bool(found)


def compose_policy_evidence(
    *,
    proposal: Any,
    impact: Mapping[str, Any] | None,
    resolves: Any,
) -> Any:
    """Attach the measured impact and the citation disclosure to a composed proposal.

    **Refuses when there is no impact** (FR-008). A proposal published with its evidence
    section missing is 037's finding in a new place: a reviewer handed a document that looks
    complete reads it as complete, and the reassurance is worse than an absent proposal.

    Mutates the proposal 041 composed rather than building a second one — there is one
    publishing path and one artefact, and a parallel composition would be the fork FR-014
    exists to prevent.
    """
    if impact is None:
        raise RequestRefused(
            "no impact measurement is attached to this proposal, so what it would permit is "
            "unknown. Publishing anyway would hand a reviewer a document that reads as "
            "complete — the reassurance this feature exists to replace",
            reason_code="impact_unavailable",
        )

    proposal.evidence.extend(render_impact_evidence(impact))

    citations, grounded = resolved_citations(getattr(proposal, "rationale", ""), resolves)
    if grounded:
        proposal.evidence.extend(render_citation_evidence(citations))
    else:
        proposal.disclosures.append(UNSUPPORTED_DISCLOSURE)
    return proposal


def render_citation_evidence(citations: list[str]) -> list[str]:
    """The evidence lines for what a proposal rests on, **split by provenance** (045, FR-016).

    A reviewer reading "this rests on your own architecture standard" is in a different
    position from one reading "this rests on a HashiCorp validated design": the first is being
    told the proposal follows a rule their organisation set, the second that it follows
    somebody else's guidance. A single undifferentiated list would let them read either as the
    other, which is the same failure the answer's per-citation provenance exists to prevent —
    one path over, where the artefact is a pull request somebody merges.

    Uses the answering path's single `provenance_of` reader rather than testing the prefix
    here. Two places deciding what a path means is how the convention decays.
    """
    from core.answering.endorsed.corpus import CUSTOMER_ENDORSED, provenance_of

    endorsed = [c for c in citations if provenance_of(c) == CUSTOMER_ENDORSED]
    validated = [c for c in citations if provenance_of(c) != CUSTOMER_ENDORSED]

    lines: list[str] = []
    if validated:
        lines.append(
            "Cited guidance that resolves against the pin: "
            + ", ".join(f"`{c}`" for c in validated)
        )
    if endorsed:
        lines.append(
            "Cited material from your organisation's endorsed sources: "
            + ", ".join(f"`{c}`" for c in endorsed)
        )
    return lines


__all__ = [
    "CITATION_PATTERN",
    "POLICY_WRITING_TOOLS",
    "PROTECTED_POLICIES_PATH",
    "SCRATCH_PREFIX",
    "PolicyAuthoringRequest",
    "ProtectedSet",
    "ProtectedSetUnavailable",
    "UNSUPPORTED_DISCLOSURE",
    "compose_policy_evidence",
    "protected_policy_hook",
    "render_citation_evidence",
    "render_impact_evidence",
    "resolved_citations",
    "read_protected_set",
]
