# SPDX-License-Identifier: Apache-2.0
"""Every conformance directory is named by a lane that will actually run its rows.

**This gap has now been paid for three times.** 010 lost a whole feature's identity rows to a
directory no lane enumerated. 014 hit the subtler form — its directory *was* named by a lane,
but by one running `-m "not host_enclave"`, which deselected exactly the rows that mattered.
018 came within one commit of the same thing, in the feature built to end this class of gap,
and its conformance contract asserted the wiring existed.

Each time the fix was a comment in the Makefile and a promise to remember. Three occurrences
is the point at which remembering is demonstrably not the mechanism.

**What makes this checkable at all** is that the failure has a shape: a row carries a marker,
a recipe line names a path and selects markers, and the two can disagree in a way nothing
observes. So the check reads both and asks whether any lane both *names* a directory and
*selects* the markers its rows carry.

It runs in `make check` rather than in a conformance lane on purpose — a check on whether the
conformance lanes are complete cannot live inside one of them.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFORMANCE = ROOT / "tests/conformance"

#: Markers that make a row invisible to a lane which does not select them.
GATED = ("enclave", "host_enclave")


def _recipe_lines() -> list[str]:
    """Every uncommented pytest invocation in a lane, joined across continuations.

    **A lane is not always a Makefile line.** 017's deployment rows run through
    `infra/bin/deployment-conformance`, which the Makefile calls — the recipe names the script
    and the script names the directory. A check that read only the Makefile would report that
    directory as unwired, which is a false alarm, and a false alarm in a hygiene check is how
    the check gets deleted.
    """
    makefile = (ROOT / "Makefile").read_text()
    # A SCRIPT ONLY COUNTS IF SOMETHING INVOKES IT.
    #
    # The first version read every script under `infra/bin` unconditionally, so a lane script
    # that existed but was called by nothing still made its directory look wired. Removing
    # the `@bash infra/bin/mcp-surface-conformance` line from the recipe left this check
    # green — which is the exact failure it exists to prevent, one level up.
    #
    # Found while wiring 019's lane, by deleting the recipe line to confirm the check bit.
    # It did not.
    sources = [ROOT / "Makefile"]
    for script in sorted((ROOT / "infra/bin").iterdir()):
        if script.is_file() and script.name in makefile:
            sources.append(script)

    lines: list[str] = []
    for source in sources:
        if not source.is_file():
            continue
        text = source.read_text(errors="ignore").replace("\\\n", " ")
        lines += [
            line
            for line in text.splitlines()
            if "pytest" in line and not line.strip().startswith("#")
        ]
    return lines


def _markers_used(directory: Path) -> set[str]:
    """The gated markers actually carried by rows in this directory."""
    used: set[str] = set()
    for module in directory.rglob("test_*.py"):
        source = module.read_text()
        for marker in GATED:
            if re.search(rf"\bmark\.{marker}\b", source):
                used.add(marker)
    return used


def _names(line: str, directory: str) -> bool:
    """Does this line collect that directory — by naming it, or by naming its parent?

    The first conformance recipe line runs the whole tree and subtracts with `--ignore`, so
    `adapter` and `mcp` are collected by a line that never says their names. A check demanding
    an explicit mention would call both unwired.
    """
    if f"conformance/{directory}" in line:
        return f"--ignore=tests/conformance/{directory}" not in line
    return "tests/conformance " in f"{line} " and (
        f"--ignore=tests/conformance/{directory}" not in line
    )


def _selects(line: str, marker: str) -> bool:
    """Would this line's marker expression run a row carrying that marker?"""
    selection = match.group(1) if (match := re.search(r'-m\s+"([^"]*)"', line)) else ""
    if f"not {marker}" in selection:
        return False
    # An empty expression runs everything; a positive one must name the marker.
    return not selection or marker in selection


def test_every_conformance_directory_is_named_by_a_lane() -> None:
    """The 010 shape: a directory nothing enumerates."""
    lines = _recipe_lines()
    unnamed = [
        d.name
        for d in sorted(CONFORMANCE.iterdir())
        if d.is_dir()
        and not d.name.startswith("__")
        and any(d.rglob("test_*.py"))
        and not any(_names(line, d.name) for line in lines)
    ]

    assert not unnamed, (
        f"conformance directories no lane enumerates: {unnamed}. Their rows pass when run by "
        f"hand and are invisible to the gate — 010 lost a feature's worth of them this way."
    )


def test_every_gated_row_has_a_lane_that_selects_it() -> None:
    """The 014 shape, which is the one that looks wired.

    A directory named on a line running `-m "not host_enclave"` is named and not run. The
    marker is what decides, and the marker is in a different file from the lane.
    """
    lines = _recipe_lines()
    orphaned: dict[str, str] = {}

    for directory in sorted(CONFORMANCE.iterdir()):
        if not directory.is_dir() or directory.name.startswith("__"):
            continue
        for marker in sorted(_markers_used(directory)):
            if not any(_names(line, directory.name) and _selects(line, marker) for line in lines):
                orphaned[f"conformance/{directory.name} [{marker}]"] = (
                    "named by a lane, but by none that selects this marker"
                )

    assert not orphaned, (
        "rows carrying a marker no lane selects:\n"
        + "\n".join(f"  {k}: {v}" for k, v in orphaned.items())
        + "\n\nThis is the trap 014 documented and 018 nearly repeated: the directory IS "
        "named by a lane, and the lane will not run the rows."
    )
