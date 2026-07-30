# SPDX-License-Identifier: Apache-2.0
"""The Qualified Model Matrix — cells, binding maps, and the two ways they refuse.

**Here, in `core.authority`, and not in `core.evals`.** A cell is an *authorization fact*:
it says a definition may use a model for a role, which is the same kind of thing as a
ceiling, authored by the same people, and un-widenable from inside a run for the same
reason. It is read on the run path at every run start. A matrix module living inside a
package named `evals` would invite somebody to import the scoring harness into a run, and
that invitation gets accepted eventually.

**Validated twice, and the second is not redundant.** Once when a definition is registered,
once when a run resolves its binding. A cell can be *withdrawn* — a model deprecated, a
suite regressed, a cell pulled after a bad result — while the definition that pinned it sits
unchanged in the registry. Validating only at registration would let a withdrawn cell keep
running because nothing re-asked. This is the reasoning that makes 010 resolve a ceiling per
run rather than caching it.

**Fallback goes to another qualified cell or the run stops.** Never to an unqualified model,
and never silently. The recording is the load-bearing half: a fallback nobody can see is a
definition that does not describe what ran.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal, Protocol

from core.authority.errors import ResolutionRefused

#: The closed role vocabulary (ADR-0039). Cells are (pack × model × role); the third
#: dimension is what ADR-0039 adds, and a reader keying on (pack, model) alone would pass
#: every other row in this module while silently permitting `write` because `summarize` was
#: qualified.
Role = Literal["ask", "plan", "write", "judge", "summarize"]
ROLES: Final[frozenset[str]] = frozenset({"ask", "plan", "write", "judge", "summarize"})

#: What qualified a cell. `fixture` means qualified against a **recording**; `live` means a
#: real model answered. Carried per cell because the difference is invisible otherwise, and
#: it matters most for `write` — a model permitted to make changes.
QualifiedBy = Literal["fixture", "live"]

#: `provider/model@version`. Enforced at parse rather than only at lookup, because an alias
#: or a bare name IS the moving target FR-011 forbids: "latest" resolving differently next
#: week is auto-tracking whether or not anything calls it that. Catching it at the
#: identifier means a matrix cannot even express one.
MODEL_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*@[A-Za-z0-9][\w.\-]*$")

SUPPORTED_SCHEMA_VERSION: Final[int] = 1


@dataclass(frozen=True)
class QualifiedCell:
    """One green cell. Only evaluation makes one, and only an operator writes one."""

    pack: str
    model: str
    role: Role
    qualified_by: QualifiedBy
    #: Which judge scored it. Empty only for the seed-qualified first judge, which is the
    #: single case where nothing above it exists — every other cell names one, and a cell
    #: recorded without a judge is refused.
    judge: str = ""
    withdrawn: bool = False

    @property
    def reference(self) -> str:
        return f"{self.pack}:{self.model}:{self.role}"


class MatrixSource(Protocol):
    """Where cells come from. The control-plane trust fabric, in practice.

    Read-only to runs, on the 010 ceiling pattern: operator-authored, and refused loudly
    when absent rather than resolving to empty. An empty matrix and an unreachable one are
    different failures, and treating the second as the first would make every definition
    look unqualified during an outage.
    """

    def read_matrix(self) -> Mapping[str, Any]:
        """Return the raw matrix record, or raise ResolutionRefused."""
        ...


def parse_matrix_record(record: Mapping[str, Any]) -> dict[str, QualifiedCell]:
    """Validate a matrix record into cells keyed by reference.

    Refuses an unsupported schema version the way `parse_ceiling_record` does — absent and
    newer land in the same place, because a record with no version is either older than
    versioning or hand-written, and both are cases where guessing is how a matrix gets
    misread.
    """
    version = record.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise ResolutionRefused(
            f"matrix record declares schema_version {version!r}; this platform understands "
            f"{SUPPORTED_SCHEMA_VERSION}",
            reason_code="unsupported_schema_version",
        )

    cells: dict[str, QualifiedCell] = {}
    for entry in record.get("cells") or ():
        cell = _parse_cell(entry)
        cells[cell.reference] = cell
    return cells


def _parse_cell(entry: Mapping[str, Any]) -> QualifiedCell:
    try:
        pack = str(entry["pack"])
        model = str(entry["model"])
        role = str(entry["role"])
        qualified_by = str(entry["qualified_by"])
    except KeyError as exc:
        raise ResolutionRefused(
            f"matrix cell missing required field: {exc}", reason_code="malformed_record"
        ) from exc

    if role not in ROLES:
        raise ResolutionRefused(
            f"matrix cell declares role {role!r}, outside the closed vocabulary {sorted(ROLES)}",
            reason_code="malformed_record",
        )
    if qualified_by not in ("fixture", "live"):
        raise ResolutionRefused(
            f"matrix cell declares qualified_by {qualified_by!r}; a cell must say whether it "
            f"was qualified against a recording or a live model",
            reason_code="malformed_record",
        )
    if not MODEL_IDENTIFIER.match(model):
        raise ResolutionRefused(
            f"model identifier {model!r} is not provider/model@version; an alias or a bare "
            f"name is a moving target, which is auto-tracking under another name (FR-011)",
            reason_code="malformed_record",
        )

    return QualifiedCell(
        pack=pack,
        model=model,
        role=role,  # type: ignore[arg-type]
        qualified_by=qualified_by,  # type: ignore[arg-type]
        judge=str(entry.get("judge") or ""),
        withdrawn=bool(entry.get("withdrawn", False)),
    )


@dataclass(frozen=True)
class MatrixFallback:
    """A pinned cell was unavailable and another qualified cell was used.

    **Returned, never written here.** The module that resolves a fallback holds no audit
    sink and no `tenant_id`, and `AuditEntry` requires both — so this travels back to
    whoever owns the sink, exactly as `AuthorityRefuseError` travels back to whoever records
    `AUTHORITY_REFUSED`. The alternative, threading a sink down here, would put audit
    writing inside authority resolution and give two modules a reason to write the same
    event.
    """

    role: Role
    pinned_cell: str
    used_cell: str
    reason: str

    def as_payload(self, *, run_id: str) -> dict[str, str]:
        return {
            "run_id": run_id,
            "role": self.role,
            "pinned_cell": self.pinned_cell,
            "used_cell": self.used_cell,
            "reason": self.reason,
        }


def validate_binding_map(
    binding_map: Mapping[str, str],
    cells: Mapping[str, QualifiedCell],
    *,
    agent_definition_id: str,
) -> None:
    """Every entry references a qualified, un-withdrawn cell — or refuse, naming it.

    Naming the cell is not decoration. "This definition is invalid" sends somebody to read
    the definition; "cell vault:anthropic/claude@1:write is not qualified" sends them to the
    matrix, which is where the fix is.
    """
    for role, reference in sorted(binding_map.items()):
        if role not in ROLES:
            raise ResolutionRefused(
                f"definition {agent_definition_id!r} binds role {role!r}, outside the closed "
                f"vocabulary {sorted(ROLES)}",
                reason_code="malformed_record",
            )
        cell = cells.get(reference)
        if cell is None:
            raise ResolutionRefused(
                f"definition {agent_definition_id!r} pins cell {reference!r} for role "
                f"{role!r}, which evaluation has not qualified",
                reason_code="unqualified_cell",
            )
        if cell.withdrawn:
            raise ResolutionRefused(
                f"definition {agent_definition_id!r} pins cell {reference!r}, which was "
                f"qualified once and has since been withdrawn",
                reason_code="cell_withdrawn",
            )
        if cell.role != role:
            # The dimension ADR-0039 exists to add. A cell qualified to `summarize` does not
            # qualify a model to `write`, and a reader that ignored `role` would pass every
            # other check in this module.
            raise ResolutionRefused(
                f"definition {agent_definition_id!r} binds cell {reference!r} to role "
                f"{role!r}; that cell is qualified for {cell.role!r}",
                reason_code="unqualified_cell",
            )


def resolve_with_fallback(
    role: Role,
    pinned: str,
    cells: Mapping[str, QualifiedCell],
    *,
    available: frozenset[str],
    agent_definition_id: str,
) -> tuple[QualifiedCell, MatrixFallback | None]:
    """The pinned cell, or another qualified one, or stop.

    ``available`` is the set of model identifiers reachable right now. A cell that is
    qualified but whose model is unavailable is the case this exists for.

    **There is no third branch.** Every path out of this function either returns a cell that
    is present in the matrix, un-withdrawn, and qualified for this exact role, or raises.
    That is what SC-004 means by "zero paths exist by which a run reaches an unqualified
    model" — not that the unqualified branch is guarded, but that there is no unqualified
    branch to guard.
    """
    cell = cells.get(pinned)
    if cell is not None and not cell.withdrawn and cell.model in available:
        return cell, None

    reason = (
        "cell_withdrawn"
        if cell is not None and cell.withdrawn
        else "model_unavailable"
        if cell is not None
        else "unqualified_cell"
    )

    candidates = sorted(
        (c for c in cells.values() if c.role == role and not c.withdrawn and c.model in available),
        key=lambda c: c.reference,
    )
    if not candidates:
        raise ResolutionRefused(
            f"definition {agent_definition_id!r} pinned {pinned!r} for role {role!r}, which is "
            f"unavailable, and no other qualified cell exists for that role; the run stops "
            f"rather than proceeding unqualified",
            reason_code="no_qualified_fallback",
        )

    chosen = candidates[0]
    return chosen, MatrixFallback(
        role=role, pinned_cell=pinned, used_cell=chosen.reference, reason=reason
    )


__all__ = [
    "MODEL_IDENTIFIER",
    "ROLES",
    "SUPPORTED_SCHEMA_VERSION",
    "MatrixFallback",
    "MatrixSource",
    "QualifiedBy",
    "QualifiedCell",
    "Role",
    "parse_matrix_record",
    "resolve_with_fallback",
    "validate_binding_map",
]
