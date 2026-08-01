# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — every claim traces to a record, and nothing is composed (021, US1).

ADR-0018's one-line summary is *reports are presentation; attestation rests on records*. These
rows assert the first half literally: for every statement a report makes, there is a record it
came from, and nothing anywhere composes one.

**Hermetic by construction, which is the point of the seam.** The compiler takes entries and
returns a report — no enclave, no product, no tenant, no HTTP request — so the rows that matter
most cannot stop running for infrastructure reasons. A gate that needs a stack is a gate that
eventually gets skipped.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from core.reports import ClaimStatus, RunReport, compile_report
from core.reports.compile import REFUSED, RUNNING
from tests.harness import recorded_runs as fixtures

ROOT = Path(__file__).resolve().parents[3]

OBSERVERS = frozenset({"vault_write"})


def _report(
    fixture: Any, *, terminal: bool = True, observers: frozenset[str] = OBSERVERS
) -> RunReport:
    return compile_report(fixture(), run_id="run-fixture", observers=observers, terminal=terminal)


@pytest.mark.parametrize("fixture", fixtures.ALL_FIXTURES, ids=fixtures.recorded_run_ids())
def test_every_claim_traces_to_a_record(fixture: Any) -> None:
    """FR-001, SC-001 — no claim without evidence behind it.

    Every fixture, not one: a compiler that populated evidence for the shapes it recognised and
    left it empty for the rest would pass a single-fixture row and fail here, and "the shapes it
    recognised" is exactly where a report drifts as the trail grows.
    """
    report = _report(fixture)
    assert report.claims, f"{fixture.__name__} produced no claims at all"

    # The entries a claim may cite, in the form the compiler writes them.
    available = {f"{e.correlation_id}#{e.seq}" for e in fixture()}
    for claim in report.claims:
        assert claim.evidence, f"claim {claim.statement!r} carries no evidence"
        unknown = set(claim.evidence) - available
        assert not unknown, (
            f"claim {claim.statement!r} cites {unknown}, which is not among the records it was "
            f"compiled from — a claim pointing at a record that is not there is worse than one "
            f"pointing at nothing, because it reads as traceable"
        )


def test_nothing_is_composed() -> None:
    """FR-001, SC-001 — **0** claims originate from a model.

    By source inspection over `src/core/reports/`, and **parsed rather than grepped**: 020's
    equivalent row matched its own prose on the first attempt, and this repository has paid for
    text-matching five times. An import is an import in the AST and a word in a docstring is a
    string.

    The compiler must reach no provider, no adapter, and no framework. It is core, so the
    layering guard already forbids a framework import — this asserts the narrower property that
    it reaches nothing that could *answer* a question, which is what "composed" would require.
    """
    forbidden = {"anthropic", "openai", "pydantic_ai", "adapters"}
    offenders: list[str] = []
    for path in (ROOT / "src/core/reports").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name in forbidden:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: {name}")
    assert not offenders, (
        f"the report compiler reaches something that can answer a question: {offenders}. "
        "Every claim must come from a record; a compiler that can ask has a second source."
    )


def test_the_compiler_holds_no_credential_and_no_query() -> None:
    """The Principle IV property, asserted rather than trusted.

    021's Constitution Check failed because read-back at report time would have run under the
    API surface's identity. The resolution moved observation into the allocation — and what
    keeps it there is that the compiler has nothing to observe *with*.

    So: no import of an identity fabric, an evidence query, or an observer implementation. A
    future change that gave the compiler any of them would have to add one of these names, which
    is visible in review rather than a silent regression.
    """
    forbidden = {
        "IdentityFabric",
        "EvidenceQuery",
        "EvidenceQueryRequest",
        "VaultDatabaseCredentials",
        "SubjectScopedVaultFabric",
        "Observer",
    }
    offenders: list[str] = []
    for path in (ROOT / "src/core/reports").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in forbidden:
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: {alias.name}")
    assert not offenders, (
        f"the compiler imports something it could read or observe with: {offenders}. "
        "That is the capability 021's Constitution Check removed — a report must not exceed "
        "its reader, and it cannot if it holds nothing to exceed them with."
    )


def test_a_denial_always_appears() -> None:
    """FR-003, SC-002 — a report that omits what was refused describes a different run."""
    report = _report(fixtures.run_with_a_denial)
    refusals = [c for c in report.claims if "refused" in c.statement]
    assert refusals, (
        f"a run containing a denial produced a report mentioning none: "
        f"{[c.statement for c in report.claims]}"
    )
    assert any("out_of_scope" in c.statement for c in refusals), (
        "the refusal appears but not its reason; a reader learns something was denied and "
        "nothing about why"
    )


def test_a_resumed_run_is_not_reported_as_incomplete() -> None:
    """FR-011 — `STEP_REOBSERVED` is *observed, not re-run*, never a gap.

    A resumed run's earlier steps carry no outcome of their own, because the allocation that ran
    them died before writing one. A compiler reading that absence as missing would describe
    every resumed run as incomplete — and resumption is the platform's headline durability
    property, so that report would be wrong about the thing it most wants to be right about.
    """
    report = _report(fixtures.resumed_run)
    reobserved = [c for c in report.claims if "re-observed" in c.statement]
    assert reobserved, "the resumed prefix produced no claim at all"
    for claim in reobserved:
        assert claim.status is ClaimStatus.FROM_RECORD, (
            f"a re-observed step is reported as {claim.status.value}; it is a recorded fact "
            f"about a step that already happened, not a gap"
        )


def test_a_refused_run_still_reports() -> None:
    """The edge case analysis pass 2 found stated in the spec and touched by no task.

    A run whose authority was refused never started: no steps, no tools, no terminal
    checkpoint. **Every other branch of the compiler is written for runs that started**, so the
    natural implementation reads the absence as `running` and reports a refused run as in
    flight — forever, and to everyone.

    It is also the first report anyone requests in anger, because a run that refused is the one
    people come asking about.
    """
    report = _report(fixtures.refused_before_starting)
    assert report.disposition == REFUSED, (
        f"a refused run reports as {report.disposition!r}; it is finished, not in flight"
    )
    assert report.disposition != RUNNING
    assert report.claims, "a refused run produced no claims; there is a trail and it says why"
    assert any("refused" in c.statement for c in report.claims)


def test_no_secret_values_reach_a_report() -> None:
    """GATE:no-secret-leak — FR-009.

    A report is the widest-aperture consumer of the trail in the platform: it reads everything
    a run recorded. Tool arguments are hashed and secret values never enter the trail, so the
    property holds upstream — this asserts the compiler does not undo it by reaching into a
    payload wholesale.

    The fixtures carry a planted credential-shaped value in a payload the compiler is not
    supposed to copy out. If a claim's text contains it, something is serialising payloads
    rather than reading named fields.
    """
    planted = "AKIA" + "EXAMPLEPLANTEDVALUE"
    entries = fixtures.clean_run()
    entries.append(
        fixtures.entry(
            entries[0].event_type,
            {"unexpected_field": planted},
            seq=99,
        )
    )
    report = compile_report(entries, run_id="run-fixture", observers=OBSERVERS, terminal=True)
    rendered = " ".join(f"{c.subject} {c.statement} {' '.join(c.evidence)}" for c in report.claims)
    assert planted not in rendered, (
        "a payload value the compiler was never asked for appears in a claim — something is "
        "serialising whole payloads instead of reading the fields it understands, which is how "
        "a secret reaches an artifact people forward"
    )
