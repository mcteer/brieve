# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — one compiled object, two consumers, and nothing reads a report (021).

**The requirement here came from a maintainer's answer**, not from the draft spec: a report
serves the human and the gate, for different purposes, from the same data. That produced FR-015a
— a gate scoring a different object from the one a person reads is not gating what anyone sees,
which is this platform's recurring failure shape given a row instead of being left available as
an implementation shortcut.
"""

from __future__ import annotations

import ast
from pathlib import Path

from core.evals.fidelity import score_fidelity
from core.reports import compile_report
from tests.harness import recorded_runs as fixtures

ROOT = Path(__file__).resolve().parents[3]
OBSERVERS = frozenset({"vault_write"})


def test_the_gate_scores_what_a_person_reads() -> None:
    """FR-015, FR-015a, FR-015c, SC-009 — the same claim set reaches both consumers.

    The fidelity gate scores `compile_report`'s output. A person requesting a report receives
    `report_for`'s output, which is `compile_report` plus validation and the governed read. This
    asserts the **claims** are the same object rather than two renderings that happen to agree —
    the gate must not be scoring a variant nobody sees.
    """
    for fixture in fixtures.ALL_FIXTURES:
        entries = fixture()
        scored = compile_report(entries, run_id="run-fixture", observers=OBSERVERS, terminal=True)
        # What the gate measures, and what a reader would see, come from one compilation.
        mentioned = {claim.subject for claim in scored.claims if claim.subject}
        score = score_fidelity(scored, sorted(mentioned))
        assert score.recall == 1.0, (
            f"{fixture.__name__}: the gate cannot see claims the report contains — it is "
            f"scoring a projection rather than the object"
        )
        assert not score.invented


def test_there_is_no_gate_only_variant() -> None:
    """FR-015a — structurally, not by inspection.

    A second compile path is how this goes wrong: someone adds `compile_for_scoring` because the
    gate wants slightly different shaping, and from then on the gate certifies something no
    reader receives. There is exactly one entry point, and this fails if a second appears.
    """
    entry_points = set()
    for path in (ROOT / "src/core/reports").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("compile"):
                entry_points.add(node.name)
    assert entry_points == {"compile_report"}, (
        f"the reports package exposes more than one compilation: {sorted(entry_points)}. A "
        f"second one is how a gate comes to score an object nobody reads."
    )


def test_nothing_reads_a_report() -> None:
    """FR-014, SC-008 — **0** code paths consume a report to decide anything.

    *Reports are presentation; attestation rests on records.* A report may render, summarise and
    prioritise; it may not be the source of any claim. So nothing in `src/` outside the reports
    package and its two surface bindings may import it — the moment something does, a compiled
    artifact starts influencing behaviour and the ADR's line is gone.

    Parsed, not grepped: the word "report" is everywhere in this codebase's prose.
    """
    allowed = {
        Path("src/core/reports"),
        Path("src/surfaces/api/reports.py"),
        Path("src/surfaces/mcp/transport.py"),  # dispatch only; reaches report_for
        Path("src/surfaces/api/app.py"),  # router registration
    }
    offenders: list[str] = []
    for path in (ROOT / "src").rglob("*.py"):
        rel = path.relative_to(ROOT)
        if any(rel == a or a in rel.parents for a in allowed):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            module = ""
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = ",".join(a.name for a in node.names)
            if "core.reports" in module or "api.reports" in module:
                offenders.append(f"{rel}:{getattr(node, 'lineno', 0)}")
    assert not offenders, (
        f"these read a report: {offenders}. Nothing may consume one to decide anything — "
        f"attestation rests on records, and a report that something acts on has become a source."
    )


def test_the_contract_states_what_this_gate_does_not_assert() -> None:
    """ADR-0047 — the limits are written down, and checked rather than trusted.

    **The limit most likely to be misread is that a report is present-tense.** Observations are
    facts about run-end; a product changed a week later reads identically to one that never
    changed. The word "verified" invites a tense the claim does not have, and that is the
    deliberate cost of making read-back run under an authority bounded by the run rather than by
    the reader.

    Checked because a contract's "what this does not assert" section rots first: it costs nothing
    to leave behind when the rows change, and nobody notices until the gate is cited for a claim
    it never made.
    """
    contract = (ROOT / "specs/021-grounded-run-reports/contracts/conformance.md").read_text()
    for required in (
        "Not that the report is present-tense",
        "Not that the run was correct",
        "Not that the records are complete",
        "Not that fidelity generalises",
    ):
        assert required in contract, (
            f"the conformance contract no longer records the limit {required!r}; a gate whose "
            f"stated limits have gone missing will be cited for claims it cannot make"
        )
