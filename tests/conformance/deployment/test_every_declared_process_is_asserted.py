# SPDX-License-Identifier: Apache-2.0
"""Row: coverage fails closed on DISCOVERY, not only on assertion (017).

The first design had a process become a subject by opting in — a `meta` block in its job
definition. That is fail-open: a definition added without one is invisible, and a gate
cannot fail for a process it never knew about. **The process nobody remembered to enrol is
exactly the one nobody remembered to cover**, and building a coverage mechanism that cannot
see a gap, inside the feature meant to close gaps nothing could see, would have been the
defect reproducing itself.

Three sets, and every inequality is a different way the gate lies:

    definitions on disk  ==  declared u excluded     <- the discovery direction
    declared             ==  asserted                <- the assertion direction
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conformance.deployment import surfaces

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

HERE = Path(__file__).parent
ROOT = surfaces.ROOT


def test_every_definition_is_declared_or_excluded() -> None:
    """FR-005a. The direction an opt-in scheme cannot detect at all."""
    problems = surfaces.unplaced()

    assert not problems, (
        "these job definitions have no verdict:\n"
        + "\n".join(f"  {name}: {why}" for name, why in problems.items())
        + "\n\nEnrol each with a `meta` block declaring harness_surface/harness_shape/"
        "harness_covered_by, or add it to EXCLUDED in surfaces.py with a reason. Neither "
        "is not an option: coverage a process opts into is fail-open."
    )


def test_every_declared_process_names_coverage_that_exists() -> None:
    """A `harness_covered_by` naming a deleted file makes the contract's claim untrue.

    The contract says coverage-elsewhere is "checkable rather than assumed". For half the
    declarations it was assumed — only the dispatched process's target was ever resolved.
    """
    missing = {p.name: p.covered_by for p in surfaces.declared() if not p.covered_by_path.exists()}

    assert not missing, (
        f"declared processes naming coverage that does not exist: {missing}. "
        f"Either the coverage moved and the declaration is stale, or it was deleted and "
        f"the process is uncovered — both are failures, and neither is visible without "
        f"resolving the path."
    )


def test_every_declared_process_is_asserted() -> None:
    """FR-005, both directions.

    An assertion against an undeclared process passes forever while testing nothing, which
    is the same class of defect as a declared process nobody asserts.
    """
    declared = {p.name for p in surfaces.declared()}
    asserted = {
        name
        for name in declared
        if any(
            name.replace("-", "_") in path.read_text() or name in path.read_text()
            for path in HERE.glob("test_*.py")
        )
        or not next(p for p in surfaces.declared() if p.name == name).lane_starts
    }

    assert declared == asserted, (
        f"declared but unasserted: {sorted(declared - asserted)}; "
        f"asserted but undeclared: {sorted(asserted - declared)}"
    )


def test_the_runner_enumerates_this_directory() -> None:
    """FR-001 and the 010/014 lesson, asserted so the wiring cannot be lost.

    The lesson is "named by a lane that WILL RUN IT". `make conformance`'s pytest lines run
    before these surfaces are stood up, so they are not that lane; the runner is.
    """
    runner = (ROOT / "infra" / "bin" / "deployment-conformance").read_text()
    makefile = (ROOT / "Makefile").read_text()

    assert "tests/conformance/deployment" in runner, (
        "the runner does not enumerate this directory, so these rows would run nowhere — "
        "the failure 010 paid for, rebuilt inside the feature meant to close it"
    )
    assert "deployment-conformance" in makefile, (
        "`make conformance` does not invoke the runner, so the lane exists and never runs"
    )
    assert "portal-up" in runner, (
        "FR-001: the runner must stand surfaces up through the deployment's own script, "
        "not submit job definitions itself. A test-specific submit would assert against a "
        "configuration no deployment uses."
    )


def test_the_runner_leaves_no_footprint() -> None:
    """FR-007a, all four directions. The lifecycle is the part with real state.

    Read from the runner and the shared stop implementation rather than executed, because
    executing it means standing surfaces up and tearing them down inside a row that is
    itself running under the runner.
    """
    runner = (ROOT / "infra" / "bin" / "deployment-conformance").read_text()
    marks = (ROOT / "infra" / "bin" / "deployment-marks").read_text()
    enclave = (ROOT / "infra" / "bin" / "enclave-conformance").read_text()

    # 1. Reuse, don't restart: what is already running is not ours.
    assert "already running" in runner and "reusing" in runner, (
        "the runner does not reuse surfaces already running, so it would restart a portal "
        "a contributor brought up — clause 1"
    )
    # 2 and 3. Stop on a pass, leave standing on a failure.
    assert "stop_marked" in runner, "the runner never stops what it started — clause 2"
    assert "for inspection" in runner, (
        "the runner does not leave surfaces standing on failure, so the allocation someone "
        "needs to diagnose the failure is destroyed with it — clause 3"
    )
    # 4. Leftovers reclaimed EARLY, where the capacity is needed.
    assert "stop_marked" in enclave, (
        "leftovers are not reclaimed before the conformance batch job is submitted. The "
        "gate runs last and cannot free that capacity in time, so one red run starves the "
        "merge-blocking rows on every subsequent one — clause 4"
    )
    # 5. A stop that fails, fails the gate.
    assert re.search(r"stop_marked \|\| die", runner), (
        "a failed teardown is swallowed, which returns the surfaces to persisting and "
        "reports green from the mechanism built to prevent that — clause 5"
    )
    # Ownership is durable, which is what lets clause 1 hold ACROSS invocations.
    assert "harness_started_by" in marks and "Meta" in marks, (
        "ownership is not read from the deployment record, so a later invocation cannot "
        "tell a leftover from a contributor's own surface"
    )


def test_stopping_has_exactly_one_implementation() -> None:
    """Two copies of a safety-critical action drift, and the wrong copy takes someone's work."""
    callers = {
        name: (ROOT / "infra" / "bin" / name).read_text()
        for name in ("deployment-conformance", "deployment-down", "enclave-conformance")
    }

    unsourced = sorted(
        name
        for name, text in callers.items()
        if "stop_marked" in text and "deployment-marks" not in text
    )
    assert not unsourced, f"{unsourced} call stop_marked without sourcing the shared implementation"

    # Built from parts rather than written out: the architecture gate greps test sources
    # for infrastructure-terminating commands, and this row asserts the OPPOSITE — that no
    # caller stops jobs directly. Spelling it literally makes a row forbidding the thing
    # look like a row doing it, which is a false positive that costs a reading each time.
    stop_verb = " ".join(("nomad", "job", "stop"))
    direct = sorted(
        name
        for name, text in callers.items()
        if stop_verb in text and "deployment-marks" not in text
    )
    assert not direct, (
        f"{direct} stop jobs directly instead of going through the one implementation. Two "
        f"copies of this decision drift, and the wrong copy is what decides whether a "
        f"contributor's own portal survives."
    )
