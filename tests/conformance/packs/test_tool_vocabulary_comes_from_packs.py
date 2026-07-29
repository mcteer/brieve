# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — no hardcoded tool-name set survives where a real ceiling is resolved.

`parse_ceiling_record` refuses any ceiling naming a tool outside the known set. So a stale
constant does not fail as "stale constant" — it fails as `unknown_ceiling_entry`, an error
that **names the ceiling**, and whoever reads it goes to look at the ceiling and at the
trust fabric. Both are fine. The stale literal in a surface module is what is wrong, and
nothing points there.

Before 013 the vocabulary lived in four places. **Three copies of a constant is how the
fourth gets missed**, so this asserts derivation structurally rather than trusting that
somebody will update all of them.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: The fixture toolset, as a literal. Any module that spells this out is declaring the
#: vocabulary rather than deriving it.
FIXTURE_TOOLS = {"echo", "plan", "apply"}

#: The one declared exemption, and its reason, on the `ENCLAVE_PATHS` pattern — an allowlist
#: whose membership is asserted, so adding a second is a decision somebody makes on the
#: record rather than a line that slips in.
#:
#: `tests/unit/test_ceiling_record_shape.py` is a hermetic unit row about the **parser**.
#: Pulling pack loading into it would put content on the fast lane to test something that
#: has nothing to do with packs, and the row would then fail for reasons unrelated to what
#: it asserts.
EXEMPT = {"tests/unit/test_ceiling_record_shape.py"}

#: Where a real ceiling is resolved: a stale vocabulary here refuses a correct record.
SEARCHED = ("src", "tests/conformance")


#: This file, which necessarily spells out the names it searches for. Excluded by identity
#: rather than added to `EXEMPT`, because the two mean different things: `EXEMPT` is a
#: decision about a module that *may* declare the vocabulary, and this is a checker that
#: cannot describe what it looks for without containing it. Folding the second into the
#: first would put a permanent entry in a list whose whole value is that entries are rare.
SELF = Path(__file__).resolve().relative_to(ROOT)


def _candidate_files() -> list[Path]:
    return [
        path
        for base in SEARCHED
        for path in (ROOT / base).rglob("*.py")
        if (relative := str(path.relative_to(ROOT))) not in EXEMPT and relative != str(SELF)
    ]


def _literal_toolsets(path: Path) -> list[str]:
    """Assignments whose value is a set/frozenset literal of the fixture tool names."""
    try:
        tree = ast.parse(path.read_text(), filename=str(path))
    except SyntaxError:  # pragma: no cover - a file that does not parse is a different bug
        return []

    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if isinstance(value, ast.Call) and getattr(value.func, "id", "") == "frozenset":
            value = value.args[0] if value.args else value
        if not isinstance(value, (ast.Set, ast.List, ast.Tuple)):
            continue
        elements = {e.value for e in value.elts if isinstance(e, ast.Constant)}
        if FIXTURE_TOOLS.issubset(elements):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            found.extend(names)
    return found


def test_no_module_declares_the_tool_vocabulary_as_a_literal() -> None:
    offenders = {
        str(path.relative_to(ROOT)): names
        for path in _candidate_files()
        if (names := _literal_toolsets(path))
    }
    assert not offenders, (
        f"these declare the tool vocabulary instead of deriving it: {offenders}. A pack "
        f"declaring a new tool makes a correct ceiling record refuse `unknown_ceiling_entry`, "
        f"and that error names the ceiling rather than the stale constant"
    )


def test_the_exemption_still_exists_and_still_needs_exempting() -> None:
    """An allowlist entry for a file that no longer qualifies is an allowlist that lies.

    If someone later derives the vocabulary in the unit row too, this fails and the
    exemption should be deleted rather than left as a permission nobody needs.
    """
    for relative in EXEMPT:
        path = ROOT / relative
        assert path.is_file(), f"exemption names {relative}, which does not exist"
        assert _literal_toolsets(path), (
            f"{relative} no longer declares a literal toolset; remove it from EXEMPT rather "
            f"than leaving an exemption nothing needs"
        )


def test_the_check_fires_on_a_contrived_violation(tmp_path: Path) -> None:
    """A positive control. An absence check nobody has seen fire proves nothing."""
    offender = tmp_path / "stale.py"
    offender.write_text('KNOWN_TOOLS = frozenset({"echo", "plan", "apply"})\n')
    assert _literal_toolsets(offender) == ["KNOWN_TOOLS"]


def test_the_surfaces_derive_from_a_registry() -> None:
    """The positive half: the two derivation sites reference the shared builder.

    Asserted by reading the source rather than by importing, because importing
    `surfaces.api.service` pulls in the whole production assembly for a question about one
    line.
    """
    for relative in ("src/surfaces/api/service.py", "src/surfaces/dispatch/entrypoint.py"):
        body = (ROOT / relative).read_text()
        assert re.search(r"\bbuild_registry\b", body), f"{relative} does not derive its toolset"
