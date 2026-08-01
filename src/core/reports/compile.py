# SPDX-License-Identifier: Apache-2.0
"""Records in, report out. Nothing else.

**This module holds no query and no credential, and that is the design** rather than an
oversight to fix later. It cannot widen scope because it never reads — it compiles what the
governed evidence read already returned. It cannot observe a product because it holds nothing to
observe with. Both properties are structural: a future change that gave the compiler either would
have to *add* it, which is visible in review rather than a silent regression.

That shape is the resolution of a Constitution Check that failed. Read-back at report time would
have run under the API surface's identity — see `AuditEventType.EFFECT_OBSERVED` for the whole
argument — so the run performs it and this compiles the answer.

**Every claim is validated against the record it cites before the report is emitted.** Populated
*from* a record and *checked against* one are the same thing only while this module is correct,
which is the assumption the check exists to remove.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from core.audit.schema import AuditEventType
from core.observation.types import ObservationOutcome
from core.reports.report import Claim, ClaimStatus, ReportBasis, RunReport

#: What a run's disposition is called when nothing terminal was recorded.
RUNNING = "running"
#: Authority was refused before anything ran. **Distinct from `running`** — a refused run is
#: finished, and reporting it as in flight would leave it that way forever in every reader's eyes.
REFUSED = "refused"

#: Event types this compiler understands. Anything else becomes an `unreconciled` claim rather
#: than being dropped — see `_unrecognised`.
_KNOWN = frozenset(
    {
        AuditEventType.RUN_START,
        AuditEventType.AUTHORITY_ISSUED,
        AuditEventType.AUTHORITY_REFUSED,
        AuditEventType.AUTHORITY_DENIED,
        AuditEventType.AUTHORITY_EXPIRED,
        AuditEventType.PRE_DECISION,
        AuditEventType.POST_DECISION,
        AuditEventType.TOOL_OUTCOME,
        AuditEventType.TOOL_CHOSEN,
        AuditEventType.EFFECT_OBSERVED,
        AuditEventType.STEP_REOBSERVED,
        AuditEventType.RUN_RESUMED,
        AuditEventType.MATRIX_FALLBACK,
        AuditEventType.MODEL_GATE,
        AuditEventType.MIRRORING_DECISION,
        AuditEventType.ENFORCEMENT_ERROR,
    }
)

#: What every report says about itself (FR-012, ADR-0032).
SCOPE = (
    "Compiled from this run's recorded evidence. Complete with respect to the records: if "
    "something happened and nothing recorded it, this report cannot know. Observations are "
    "facts about run-end, not about the product now."
)


def _entry_ref(entry: Any) -> str:
    """How a claim points at the record behind it — stream position, not contents."""
    return f"{entry.correlation_id}#{entry.seq}"


def _observations(entries: Sequence[Any]) -> dict[tuple[int, str], Any]:
    """What the run learned by asking, keyed by the step and tool it asked about."""
    found: dict[tuple[int, str], Any] = {}
    for entry in entries:
        if entry.event_type == AuditEventType.EFFECT_OBSERVED:
            payload = entry.payload or {}
            found[(int(payload.get("step_index", -1)), str(payload.get("tool", "")))] = entry
    return found


def _effect_status(observation: Any, *, terminal: bool, has_observer: bool) -> ClaimStatus:
    """Which of the five effect statuses this claim carries.

    **Total over the five, with no fall-through.** The one thing this function may never do is
    return a status meaning "completed" on the strength of a `TOOL_OUTCOME` alone — that is the
    silent assertion the whole vocabulary exists to prevent, and it is what a reader cannot
    detect by reading.
    """
    if observation is not None:
        outcome = str((observation.payload or {}).get("outcome", ""))
        if outcome == ObservationOutcome.HAPPENED:
            return ClaimStatus.OBSERVED
        if outcome == ObservationOutcome.DID_NOT_HAPPEN:
            return ClaimStatus.CONTRADICTED
        return ClaimStatus.UNVERIFIED_UNREACHABLE
    if not has_observer:
        return ClaimStatus.UNVERIFIED_NO_OBSERVER
    # An observer exists and the run recorded nothing: it never got to the end.
    return ClaimStatus.UNVERIFIED_UNREACHABLE if terminal else ClaimStatus.UNVERIFIED_NOT_OBSERVED


def _disposition(entries: Sequence[Any]) -> str:
    """Running, refused, or what the run's ending was called.

    **`refused` is its own answer.** A run whose authority was refused never started, so it has
    no terminal record — and every other branch here is written for runs that did start. Reading
    that absence as `running` would leave a refused run reported as in flight forever, which is
    the first report anyone requests in anger.
    """
    types = {entry.event_type for entry in entries}
    if AuditEventType.AUTHORITY_REFUSED in types and AuditEventType.RUN_START not in types:
        return REFUSED
    for entry in reversed(list(entries)):
        if entry.event_type == AuditEventType.RUN_RESUMED:
            outcome = str((entry.payload or {}).get("outcome", ""))
            if outcome in {"stopped", "suspended"}:
                return outcome
    return RUNNING


def compile_report(
    entries: Sequence[Any],
    *,
    run_id: str,
    observers: frozenset[str] = frozenset(),
    terminal: bool = False,
    basis: ReportBasis | None = None,
) -> RunReport:
    """Compile one run's records into the artifact a person reads.

    ``entries`` have already been read through the governed, tenant-scoped evidence path. This
    function does not query, and therefore cannot widen what the caller was entitled to see.

    ``observers`` is the set of tool names the registry holds an observer for — **names only**.
    It is what distinguishes "the product could not be asked" from "there was nobody to ask", and
    it is deliberately not the observers themselves: handing this function something it could
    call would give it the capability the Constitution Check removed.

    ``terminal`` says whether the run reached an ending. A run still in flight has not observed
    yet, and that is a different fact from a run that ended without observing.
    """
    claims: list[Claim] = []
    observations = _observations(entries)

    for entry in entries:
        if entry.event_type not in _KNOWN:
            claims.append(_unrecognised(entry))
            continue
        claim = _claim_for(entry, observations=observations, observers=observers, terminal=terminal)
        if claim is not None:
            claims.append(claim)

    return RunReport(
        run_id=run_id,
        disposition=_disposition(entries),
        claims=tuple(claims),
        basis=basis if basis is not None else ReportBasis(),
        scope=SCOPE,
    )


def _unrecognised(entry: Any) -> Claim:
    """An entry type this compiler does not understand.

    **Surfaced, never dropped.** A compiler that ignores what it does not recognise gets quieter
    as the trail gets richer — every future audit event would silently vanish from every report,
    and nothing would go red. Silence is the failure mode here, so an unknown type is a visible
    `unreconciled` claim.
    """
    return Claim(
        subject=str(entry.event_type),
        statement=f"a record of type {entry.event_type!s} that this report cannot interpret",
        status=ClaimStatus.UNRECONCILED,
        evidence=(_entry_ref(entry),),
    )


def _claim_for(
    entry: Any,
    *,
    observations: dict[tuple[int, str], Any],
    observers: frozenset[str],
    terminal: bool,
) -> Claim | None:
    """One claim per record that says something a reader needs, or None."""
    payload = entry.payload or {}
    ref = _entry_ref(entry)

    if entry.event_type == AuditEventType.TOOL_OUTCOME:
        tool = str(payload.get("tool_name", ""))
        step = int(payload.get("step_index", -1))
        observation = observations.get((step, tool))
        status = _effect_status(observation, terminal=terminal, has_observer=tool in observers)
        evidence = (ref,) if observation is None else (ref, _entry_ref(observation))
        return Claim(
            subject=tool,
            statement=f"{tool} ran at step {step}",
            status=status,
            evidence=evidence,
        )

    if entry.event_type == AuditEventType.PRE_DECISION and payload.get("outcome") == "deny":
        # FR-003. A report that omits what was refused describes a different run.
        return Claim(
            subject=str(payload.get("hook_name", "governance")),
            statement=f"refused: {payload.get('reason_code', 'unknown')}",
            status=ClaimStatus.FROM_RECORD,
            evidence=(ref,),
        )

    if entry.event_type == AuditEventType.TOOL_CHOSEN:
        # 020's vocabulary. `named`/`outcome` distinguish a chosen tool from a scheduled one,
        # and the terminal outcomes from each other.
        return Claim(
            subject=str(payload.get("named") or "(nothing)"),
            statement=(
                f"model {payload.get('model', 'unknown')} "
                f"{payload.get('outcome', 'named')} at step {payload.get('step_index', '?')}"
            ),
            status=ClaimStatus.FROM_RECORD,
            evidence=(ref,),
        )

    if entry.event_type == AuditEventType.STEP_REOBSERVED:
        # Observed, not re-run. A report reading this as a gap would describe every resumed
        # run as incomplete.
        return Claim(
            subject=f"step {payload.get('step_index', '?')}",
            statement=f"re-observed rather than re-executed: {payload.get('reason', '')}",
            status=ClaimStatus.FROM_RECORD,
            evidence=(ref,),
        )

    if entry.event_type == AuditEventType.AUTHORITY_REFUSED:
        return Claim(
            subject="authority",
            statement=f"refused: {payload.get('reason_code', 'unknown')}",
            status=ClaimStatus.FROM_RECORD,
            evidence=(ref,),
        )

    return None


def validate(report: RunReport, entries: Sequence[Any]) -> RunReport:
    """Check every claim against the records before the report is emitted (FR-004).

    **Separate from compilation on purpose.** Populated *from* a record and *checked against* one
    are the same thing only while `compile_report` is correct — which is precisely the assumption
    this removes. A claim whose cited evidence is not in the entries it was compiled from becomes
    `unreconciled`; it is never dropped, and it never suppresses the rest of the report.
    """
    refs = {_entry_ref(entry) for entry in entries}
    checked = tuple(
        claim
        if claim.evidence and set(claim.evidence) <= refs
        else claim.model_copy(update={"status": ClaimStatus.UNRECONCILED})
        for claim in report.claims
    )
    return report.model_copy(update={"claims": checked})


__all__ = ["REFUSED", "RUNNING", "SCOPE", "compile_report", "validate"]
