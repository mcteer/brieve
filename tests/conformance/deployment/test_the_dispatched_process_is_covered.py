# SPDX-License-Identifier: Apache-2.0
"""Row: the dispatched entrypoint's coverage exists and dispatches (017, US5).

Research found this **already covered** — 014's durability rows dispatch real `agent-run`
allocations through the production dispatcher and assert completion. Three of the five known
instances of this failure class lived in that path, and they were found by building that
coverage.

What was missing is that the coverage is *incidental*: it exists because durability rows
happen to need a dispatch, not because anything asserts the dispatched process must be
covered. A change that stopped dispatching would remove it silently.

**Honest limit**: this asserts the coverage is present and of the right kind. A change that
gutted a durability row while leaving its name in place would not be caught here.
"""

from __future__ import annotations

import pytest

from tests.conformance.deployment import surfaces

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


def dispatched() -> surfaces.DeclaredProcess:
    processes = [p for p in surfaces.declared() if p.shape == "dispatched"]
    assert processes, "no process declares the dispatched shape"
    return processes[0]


def test_the_dispatched_coverage_actually_dispatches() -> None:
    """FR-013: caused to run, not read from records a previous run left behind.

    A process that can no longer start still leaves last week's evidence. Reading it would
    pass against a broken assembly, which is the liveness-check mistake one layer up.
    """
    target = dispatched().covered_by_path
    assert target.exists(), f"{target} does not exist"

    sources = list(target.glob("test_*.py")) if target.is_dir() else [target]
    dispatching = [p for p in sources if "dispatch(" in p.read_text()]

    assert dispatching, (
        f"nothing under {target} dispatches. The coverage may read records an earlier run "
        f"left behind, which a process that can no longer start would still have produced."
    )


def test_the_dispatched_coverage_is_collected_by_a_lane_that_runs_it() -> None:
    """014 found that "named by a lane" and "named by a lane that will run it" differ.

    A directory named on a line that deselects the rows is invisible while looking wired.
    """
    covered_by = dispatched().covered_by.rstrip("/")
    makefile = (surfaces.ROOT / "Makefile").read_text()

    lines = [
        line
        for line in makefile.splitlines()
        if covered_by in line and "pytest" in line and not line.strip().startswith("#")
    ]
    assert lines, f"{covered_by} is named by no pytest line in the conformance recipe"

    assert any("host_enclave" in line and "not host_enclave" not in line for line in lines), (
        f"{covered_by} is named only by lines that deselect its rows. That is exactly the "
        f"trap 014 documented: the directory IS named by a lane, and the lane will not run "
        f"the rows."
    )
