# SPDX-License-Identifier: Apache-2.0
"""Which qualified cell an ask may use — a definition's binding, for a path with no definition.

**Principle VIII applies to asking, and until 026 it did not hold.** Model use goes only through a
binding map over eval-qualified Qualified Model Matrix cells; the answering path took a provider by
injection and called it. 024's conformance contract asserted the opposite in so many words, and
nothing performed it.

**A run binds through its agent definition. An ask has neither a run nor a definition**, so the
binding is its own operator-authored record in the trust fabric, beside the ceiling and the matrix.
Deployment configuration was considered and rejected for a reason worth keeping: *where* a model is
reachable from is assembly, *which* model is permitted is governance, and a binding in a jobspec
would make this principle configurable by whoever deploys.

**This module lives in `authority`, not `answering`, and that placement is enforced.** 025's
never-acts rows read the answering path's imports and forbid any module containing `authority` —
so the obvious home for this code is the one place it must not live. The surface calls this
*before* the answering path is entered, which is also the ordering the requirement needs: 020's
entrypoint validates a cell before `build_chooser` constructs anything, so an unqualified model is
never *reached* rather than merely never used.

**No branch of its own.** `resolve_with_fallback` already returns a cell that is present,
un-withdrawn and qualified for the exact role, or raises — its docstring says there is no third
branch, and that is what makes the equivalent guarantee true for runs. This module looks up which
cell a source is bound to and hands over. Adding a decision here would be adding the branch that
one was written not to have.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from core.authority.errors import ResolutionRefused
from core.authority.matrix import (
    MatrixFallback,
    QualifiedCell,
    parse_matrix_record,
    resolve_with_fallback,
)

SUPPORTED_SCHEMA_VERSION: Final[int] = 1

#: The two things an ask can consult. Matches `core.answering.routing.Route`'s answering members —
#: duplicated as strings rather than imported, because this module must not depend on the
#: answering package it exists to gate.
GUIDANCE: Final[str] = "guidance"
ESTATE: Final[str] = "estate"
SOURCES: Final[frozenset[str]] = frozenset({GUIDANCE, ESTATE})

#: The role a SOURCE binding may name. A green `plan` cell licenses planning; roles exist
#: precisely so that one qualification does not license everything.
ASK_ROLE: Final[str] = "ask"

#: The relevance gate's binding (043). Not a source — it consults nothing — so it sits beside
#: `SOURCES` rather than in it, and every loop over sources is unchanged by its arrival.
RELEVANCE: Final[str] = "relevance"

#: The role the relevance binding may name. **A judge, not an ask** (043, FR-013): the gate
#: renders a verdict on an answer, which is judging, and a cell qualified to answer is not
#: qualified to judge. ADR-0039's closed vocabulary is not widened — this reuses `judge` under
#: its own cell identity.
RELEVANCE_ROLE: Final[str] = "judge"

#: Field name → the role that field's cell must carry. **Per field, because 043 added a field
#: whose role differs**, and the parser previously refused every non-`ask` cell outright — so
#: the record would have refused the very field being added to it. The refusal is unchanged in
#: strength and now runs in both directions: a `judge` cell in a source field and an `ask` cell
#: in the relevance field each refuse at parse.
EXPECTED_ROLE: Final[Mapping[str, str]] = {
    GUIDANCE: ASK_ROLE,
    ESTATE: ASK_ROLE,
    RELEVANCE: RELEVANCE_ROLE,
}


@dataclass(frozen=True)
class AskBinding:
    """Which cell each source is bound to, and which judges relevance. Any may be absent."""

    guidance_cell: str = ""
    estate_cell: str = ""
    #: The relevance gate's cell (043). Absent means **nobody decided**, which the surface
    #: surfaces as `relevance_unbound` before any question of availability — 026's rule.
    relevance_cell: str = ""
    #: Whether the relevance gate runs at all (044, an administrator's switch).
    #:
    #: **Absent means ENABLED**, and that default is the whole compatibility story: every
    #: binding record written before 044 carries no such field, and each one must keep meaning
    #: exactly what it meant — the gate on. A default of `False` would silently disable the
    #: relevance check across every estate the moment this field shipped, which is gap 0g
    #: reintroduced by a dataclass default.
    #:
    #: Distinct from `relevance_cell` being absent. Unbound means *nobody decided who judges*
    #: and refuses; disabled means *somebody decided not to judge* and answers with the
    #: absence disclosed. One is a gap, the other is a decision, and they read differently to
    #: whoever finds them.
    relevance_enabled: bool = True

    def cell_for(self, source: str) -> str:
        return self.guidance_cell if source == GUIDANCE else self.estate_cell


def parse_ask_binding_record(record: Mapping[str, Any]) -> AskBinding:
    """Validate an ask-binding record, refusing anything malformed.

    The ceiling's discipline, verbatim: an unsupported schema version and an absent one land in the
    same place, because a record with no version is either older than versioning or hand-written,
    and both are cases where guessing is how a binding gets misread.

    **A cell naming a role other than `ask` refuses HERE, at parse** — not later at resolution. A
    mis-authored binding should fail when someone asks about the record, not when the first person
    asks a question through it.
    """
    version = record.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise ResolutionRefused(
            f"ask-binding record declares schema_version {version!r}; this platform understands "
            f"{SUPPORTED_SCHEMA_VERSION}",
            reason_code="unsupported_schema_version",
        )

    cells: dict[str, str] = {}
    for field_name in sorted(EXPECTED_ROLE):
        raw = record.get(f"{field_name}_cell")
        if raw is None or raw == "":
            continue
        reference = str(raw)
        parts = reference.split(":")
        if len(parts) != 3:
            raise ResolutionRefused(
                f"ask-binding names {reference!r} for {field_name}; a cell reference is "
                f"pack:model:role",
                reason_code="malformed_record",
            )
        expected = EXPECTED_ROLE[field_name]
        if parts[2] != expected:
            raise ResolutionRefused(
                f"ask-binding names {reference!r} for {field_name}, whose role is {parts[2]!r} "
                f"rather than {expected!r}. A cell qualified for another role licenses that "
                f"role, not this one",
                reason_code="malformed_record",
            )
        cells[field_name] = reference

    # `is not False` rather than a truthiness check or `bool(...)`: the field is absent on
    # every pre-044 record and must read as enabled, while an explicit `false` — the only way
    # an administrator turns it off — must be honoured. A record carrying a nonsense value
    # (`"no"`, `0`) reads as enabled, which is the safe direction for a gate.
    enabled = record.get("relevance_enabled") is not False

    return AskBinding(
        guidance_cell=cells.get(GUIDANCE, ""),
        estate_cell=cells.get(ESTATE, ""),
        relevance_cell=cells.get(RELEVANCE, ""),
        relevance_enabled=enabled,
    )


def resolve_ask_cell(
    source: str,
    binding: AskBinding,
    cells: Mapping[str, QualifiedCell],
    *,
    available: frozenset[str],
) -> tuple[QualifiedCell, MatrixFallback | None]:
    """The cell this source is bound to, or another qualified one, or refuse.

    Refuses `unbound` when nothing is bound **for this source** — a binding for guidance does not
    license estate answering, or the reverse, because an operator qualifying a model to summarise
    a tenant's records has not thereby qualified it to cite documentation.

    Everything past that is `resolve_with_fallback`'s: absent, withdrawn, and wrong-role all refuse
    there, and a fallback only ever lands on another qualified `ask` cell.
    """
    if source not in SOURCES:
        raise ResolutionRefused(
            f"{source!r} is not a source an ask can consult", reason_code="malformed_record"
        )

    pinned = binding.cell_for(source)
    if not pinned:
        raise ResolutionRefused(
            f"no ask binding names a cell for {source}; an operator has not decided which model "
            f"may answer these questions",
            reason_code="unbound_ask_source",
        )

    return resolve_with_fallback(
        ASK_ROLE,  # type: ignore[arg-type]
        pinned,
        cells,
        available=available,
        # The binding stands where a definition would for a run. Named so a fallback record reads
        # as "the ask binding's pinned cell was unavailable" rather than naming a definition that
        # does not exist.
        agent_definition_id="ask-binding",
    )


def resolve_relevance_cell(
    binding: AskBinding,
    cells: Mapping[str, QualifiedCell],
    *,
    available: frozenset[str],
) -> tuple[QualifiedCell, MatrixFallback | None]:
    """The cell the relevance gate is bound to, or another qualified judge, or refuse (043).

    **`relevance_unbound` is its own reason, and it arrives before any question of
    availability.** 026's rule, applied to a second decision: "nobody decided which model may
    judge relevance" and "the model we chose cannot be reached" send an operator to the trust
    fabric and to a vendor's status page respectively, and one code for both sends them to
    argue with governance during an outage.

    Everything past the binding is `resolve_with_fallback`'s, exactly as the source path does
    it — absent, withdrawn and wrong-role all refuse there, and a fallback only ever lands on
    another qualified **judge** cell.
    """
    pinned = binding.relevance_cell
    if not pinned:
        raise ResolutionRefused(
            "no ask binding names a cell for relevance; an operator has not decided which "
            "model may judge whether an answer addresses the question",
            reason_code="relevance_unbound",
        )

    resolved, fallback = resolve_with_fallback(
        RELEVANCE_ROLE,  # type: ignore[arg-type]
        pinned,
        cells,
        available=available,
        agent_definition_id="ask",
    )

    # ADR-0067's SECOND binding point, and the one the ADR wrote down while 043 first
    # implemented only the first. `promote_model_version` refuses a matrix cell whose `judge`
    # names its own model; nothing stopped an operator BINDING relevance to the same model the
    # answering cell names, which is the same defect arriving through configuration instead of
    # through promotion — and it is the one that reaches a person, because this verdict decides
    # whether an answer is shown at all.
    #
    # Checked against the RESOLVED cell, not the pinned one: a fallback lands on a different
    # judge, and it is the model that will actually judge whose identity matters.
    #
    # Both sources, because one relevance cell serves both and the record does not say which
    # will generate. Refusing on either is the narrower reading, and a gate that permitted
    # self-judgement for one source would fail exactly when that source was asked.
    generating = {
        source: reference.split(":")[1]
        for source, reference in (
            (GUIDANCE, binding.guidance_cell),
            (ESTATE, binding.estate_cell),
        )
        if reference.count(":") >= 2
    }
    for source, model in generating.items():
        if model == resolved.model:
            raise ResolutionRefused(
                f"the relevance judge resolved to {resolved.model}, which is the model the "
                f"{source} cell names; a model does not judge its own output (ADR-0067), and "
                f"this verdict decides whether a person is shown an answer at all",
                reason_code="self_judged_relevance",
            )

    return resolved, fallback


class AskAuthority:
    """What the surface consults before an answering path exists in scope.

    Holds two readers — the binding record and the matrix record — as callables, so tests supply
    dictionaries and assembly supplies the trust fabric. Neither is constructed here.

    **An unreadable fabric is not an empty one.** `MatrixSource` already draws that line and gives
    the reason: treating an outage as "no qualified cells" would make every model look unqualified
    during an incident, which sends an operator to argue with governance instead of to the outage.
    """

    def __init__(
        self,
        *,
        read_binding: Callable[[], Mapping[str, Any]],
        read_matrix: Callable[[], Mapping[str, Any]],
    ) -> None:
        self._read_binding = read_binding
        self._read_matrix = read_matrix

    def resolve(
        self, source: str, *, available: frozenset[str]
    ) -> tuple[QualifiedCell, MatrixFallback | None]:
        """Resolve, or raise `ResolutionRefused` with the reason the trail should carry."""
        try:
            binding_record = self._read_binding()
            matrix_record = self._read_matrix()
        except ResolutionRefused:
            raise
        except Exception as exc:  # noqa: BLE001 — any read fault is a read fault
            # `fabric_unreachable`, NOT a new "matrix_unreadable" (which the spec named).
            # The platform already has this reason, meaning exactly "the trust fabric did not
            # answer" — a second name for one concept is the fragmentation Principle VII
            # forbids, and an investigator filtering for fabric outages wants one code.
            raise ResolutionRefused(
                f"the trust fabric could not be read: {type(exc).__name__}",
                reason_code="fabric_unreachable",
            ) from exc

        binding = parse_ask_binding_record(binding_record)
        cells = parse_matrix_record(matrix_record)
        return resolve_ask_cell(source, binding, cells, available=available)

    def read_binding_record(self) -> Mapping[str, Any]:
        """The raw binding record, for callers that need a field rather than a resolution.

        Public because 044 needs the relevance toggle *before* resolving anything — a disabled
        gate has no cell to resolve — and reaching for `_read_binding` from another module
        would be a private attribute becoming an interface by use rather than by decision.
        """
        record: Mapping[str, Any] = self._read_binding()
        return record

    def resolve_relevance(
        self, *, available: frozenset[str]
    ) -> tuple[QualifiedCell, MatrixFallback | None]:
        """The relevance judge's cell (043), read from the same records as the sources.

        Same fabric, same parse, same refusal vocabulary — a second reader would be a second
        answer to "what did the operator decide", and they would disagree exactly when it
        mattered.
        """
        try:
            binding_record = self._read_binding()
            matrix_record = self._read_matrix()
        except ResolutionRefused:
            raise
        except Exception as exc:  # noqa: BLE001 — any read fault is a read fault
            raise ResolutionRefused(
                f"the trust fabric could not be read: {type(exc).__name__}",
                reason_code="fabric_unreachable",
            ) from exc

        binding = parse_ask_binding_record(binding_record)
        cells = parse_matrix_record(matrix_record)
        return resolve_relevance_cell(binding, cells, available=available)


__all__ = [
    "ASK_ROLE",
    "RELEVANCE",
    "RELEVANCE_ROLE",
    "ESTATE",
    "GUIDANCE",
    "SOURCES",
    "SUPPORTED_SCHEMA_VERSION",
    "AskAuthority",
    "AskBinding",
    "parse_ask_binding_record",
    "resolve_ask_cell",
    "resolve_relevance_cell",
]
