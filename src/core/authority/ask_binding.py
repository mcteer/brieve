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

#: The only role an ask binding may name. A green `plan` cell licenses planning; roles exist
#: precisely so that one qualification does not license everything.
ASK_ROLE: Final[str] = "ask"


@dataclass(frozen=True)
class AskBinding:
    """Which cell each source is bound to. Either may be absent."""

    guidance_cell: str = ""
    estate_cell: str = ""

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
    for source in sorted(SOURCES):
        raw = record.get(f"{source}_cell")
        if raw is None or raw == "":
            continue
        reference = str(raw)
        parts = reference.split(":")
        if len(parts) != 3:
            raise ResolutionRefused(
                f"ask-binding names {reference!r} for {source}; a cell reference is "
                f"pack:model:role",
                reason_code="malformed_record",
            )
        if parts[2] != ASK_ROLE:
            raise ResolutionRefused(
                f"ask-binding names {reference!r} for {source}, whose role is {parts[2]!r} rather "
                f"than {ASK_ROLE!r}. A cell qualified for another role licenses that role, not "
                f"this one",
                reason_code="malformed_record",
            )
        cells[source] = reference

    return AskBinding(guidance_cell=cells.get(GUIDANCE, ""), estate_cell=cells.get(ESTATE, ""))


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


__all__ = [
    "ASK_ROLE",
    "ESTATE",
    "GUIDANCE",
    "SOURCES",
    "SUPPORTED_SCHEMA_VERSION",
    "AskAuthority",
    "AskBinding",
    "parse_ask_binding_record",
    "resolve_ask_cell",
]
