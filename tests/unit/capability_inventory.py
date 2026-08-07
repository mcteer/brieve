# SPDX-License-Identifier: Apache-2.0
"""Every capability this platform defines, against every one a run can reach.

**This exists because the gap shipped twice.** 036 built code mode and registered
`run_program` nowhere; 038 built authoring and registered `author_file`, `read_subject` and
`open_proposal` nowhere. Both had green conformance rows for months — the rows drove the
implementation directly, so they passed every day the capability was unreachable — and both
gaps were found by accident rather than by a gate. The second was found only because someone
asked whether the platform could write code.

A capability that is defined and unreachable is not necessarily wrong: it may be deliberately
withheld, or waiting on a successor feature. What is wrong is for nobody to know which. So the
rule is not *"everything must be reachable"* — it is **"every capability is reachable, or
recorded as deliberately not, with a reason and a record."**

**The ledger is the record; the sweep keeps the ledger honest.** A hand-maintained list would
drift the first time somebody added a capability without reading this file, which is exactly
how the two gaps happened. The sweep reads `src/core` for the shape a tool name is declared
in, so a constant the ledger has never heard of fails the row rather than joining it silently.
"""

from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE = ROOT / "src" / "core"
SURFACES = ROOT / "src" / "surfaces"


@dataclass(frozen=True)
class Withheld:
    """Why a defined capability is deliberately unreachable, and where that was decided."""

    #: One sentence a reader can act on.
    reason: str
    #: The record that decided it — an ADR, or the feature that will consume the entry.
    record: str


#: Capabilities the platform defines and deliberately does not register.
#:
#: **An entry here is a decision, not a TODO.** Each names the record that made it, so a
#: reader can tell "nobody has got to this yet" from "somebody decided this, here is why".
DELIBERATELY_UNREACHABLE: dict[str, Withheld] = {
    "run_program": Withheld(
        reason=(
            "code mode is decided against — the runtime is upstream pre-release with no "
            "timeline, and the capability was being conflated with the platform writing code, "
            "which is 038's subject"
        ),
        record="ADR-0065",
    ),
    "read_subject": Withheld(
        reason="authoring is built and not yet reachable; registering it is the successor feature",
        record="040's successor — authoring becomes reachable",
    ),
    "author_file": Withheld(
        reason="authoring is built and not yet reachable; registering it is the successor feature",
        record="040's successor — authoring becomes reachable",
    ),
    "open_proposal": Withheld(
        reason="authoring is built and not yet reachable; registering it is the successor feature",
        record="040's successor — authoring becomes reachable",
    ),
}

#: Module-level constants whose value is a tool name. The sweep looks for this shape.
#:
#: **Stated rather than inferred**, and the residual is stated with it: a capability declared
#: some other way — built at runtime, or named only at its registration call — is invisible to
#: this sweep. Narrowing that residual means parsing far more than a name is worth; what makes
#: it safe is that the convention is uniform today and this comment is where a future author
#: reads that it has to stay that way.
_NAME_SUFFIXES = ("_TOOL_NAME", "_TOOL")
_EXPLICIT_NAME_CONSTANTS = frozenset({"READ_SUBJECT", "AUTHOR_FILE", "OPEN_PROPOSAL"})


def _string_constants(path: pathlib.Path) -> dict[str, str]:
    """Module-level ``NAME = "literal"`` assignments in one file."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:  # pragma: no cover - a syntax error is somebody else's failing row
        return {}
    found: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.isupper():
                found[target.id] = node.value.value
    return found


def defined_capabilities() -> dict[str, str]:
    """Every tool name `core` declares, as ``name -> where it was declared``."""
    defined: dict[str, str] = {}
    for path in sorted(CORE.rglob("*.py")):
        for constant, value in _string_constants(path).items():
            if constant in _EXPLICIT_NAME_CONSTANTS or constant.endswith(_NAME_SUFFIXES):
                defined[value] = str(path.relative_to(ROOT))
    return defined


def registered_capabilities() -> set[str]:
    """Every tool name a run can actually reach.

    Read from the assembled registry rather than by grepping for `register(` calls: what
    matters is what a run resolves, and a registration behind a condition nobody meets is not
    reachability. The fixture toolset is what every run gets; pack tools arrive the same way
    through the same function.
    """
    from surfaces.toolset import build_registry

    registry, _ = build_registry()
    names = set(registry.tool_names())

    # Pack tools are registered through the same path, and their names live in the pack
    # manifests rather than in `core`. Included so a pack tool never reads as undefined.
    from surfaces.handlers import PLATFORM_HANDLERS

    return names | set(PLATFORM_HANDLERS)


def unaccounted() -> dict[str, str]:
    """Capabilities that are neither reachable nor recorded as deliberately withheld."""
    reachable = registered_capabilities()
    return {
        name: where
        for name, where in defined_capabilities().items()
        if name not in reachable and name not in DELIBERATELY_UNREACHABLE
    }


def stale_ledger_entries() -> set[str]:
    """Ledger entries for capabilities that are now reachable, or no longer defined.

    The other direction, and it matters as much: an entry saying *"deliberately unreachable"*
    about something a run can now reach is a record that has quietly become false, which is
    the shape this repository's roadmap warns about in its own Next section.
    """
    reachable = registered_capabilities()
    defined = set(defined_capabilities())
    return {name for name in DELIBERATELY_UNREACHABLE if name in reachable or name not in defined}


__all__ = [
    "DELIBERATELY_UNREACHABLE",
    "Withheld",
    "defined_capabilities",
    "registered_capabilities",
    "stale_ledger_entries",
    "unaccounted",
]
