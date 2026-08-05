# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the sandbox runtime is the project we meant, pinned exactly (U3).

**`uv add monty` installs the wrong project and nothing tells you.** PyPI `monty` is an
unrelated materials-science package from the pymatgen ecosystem; the sandbox this feature
depends on publishes as `pydantic-monty` (import name `pydantic_monty`). The wrong package
resolves cleanly, installs cleanly, and fails only at the import — by which point the
mistake looks like a bug in our code rather than in a dependency line.

ADR-0004's discipline is that adopted content is adopted by IDENTITY, not by a name that
looked right once. That has always been applied to documents here; this applies it to a
runtime dependency, which is the first time the platform has taken one on the governed
path.

**The pin is exact, and that is also asserted.** Upstream is `0.0.x` by its own versioning
and moved twice in the week around ADR-0054, with a banner reading "Experimental — not
ready for prime time". FR-014a puts the platform in charge of the sandbox seam precisely so
the runtime underneath is replaceable — and a floor (`>=`) would let a replacement arrive
without anybody choosing it.
"""

from __future__ import annotations

import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
PYPROJECT = REPO / "pyproject.toml"

#: The correct distribution, exactly pinned. `pydantic-monty==0.0.19`, not `monty`, not a
#: floor. Matched with the version left open so a deliberate bump does not fail this row —
#: what is asserted is the NAME and the EXACTNESS, not one particular version.
_CORRECT = re.compile(r'"pydantic-monty==\d+\.\d+\.\d+"')

#: The trap. A dependency entry whose distribution name is bare `monty`, in any form —
#: `"monty"`, `"monty==...'`, `"monty>=..."`. Word-boundaried on the left so
#: `pydantic-monty` does not match, which is the whole point of the check.
_WRONG = re.compile(r'"(?<![\w-])monty(?![\w-])')


def _dependency_lines() -> list[str]:
    """Every line of `pyproject.toml` that declares a dependency.

    Prose is excluded by structure rather than by keyword: a dependency entry is a quoted
    string inside a list, and a comment starts with `#`. The comments in `pyproject.toml`
    discuss the `monty` trap by name — deliberately, because that is where an author would
    read about it — so a checker matching the whole file would fail on the very passage
    that prevents the mistake. This is the prose-versus-substance error this repository has
    now made in 006's boundary checker, 007's run-reference check, 008's read-path
    isolation test, and 027's conformance-marker check.
    """
    lines = []
    for raw in PYPROJECT.read_text().splitlines():
        stripped = raw.strip()
        if stripped.startswith("#"):
            continue
        lines.append(raw)
    return lines


def test_the_check_covers_something() -> None:
    """Without this, a moved or renamed pyproject would make every assertion vacuous."""
    lines = _dependency_lines()
    assert len(lines) > 50, "pyproject.toml did not parse into dependency lines"
    assert any("pydantic-ai-slim" in line for line in lines), (
        "the comment stripper removed real dependency entries"
    )


def test_the_sandbox_runtime_is_pydantic_monty_pinned_exactly() -> None:
    declared = [line for line in _dependency_lines() if "monty" in line.lower()]
    assert declared, "no sandbox runtime is declared; the `sandbox` extra is missing"
    for line in declared:
        assert _CORRECT.search(line), (
            f"sandbox runtime must be `pydantic-monty==<exact>`, found: {line.strip()}"
        )


def test_the_wrong_project_is_not_a_dependency() -> None:
    """Bare `monty` is a different project entirely — see the module docstring."""
    offenders = [line.strip() for line in _dependency_lines() if _WRONG.search(line)]
    assert offenders == [], (
        "PyPI `monty` is the pymatgen materials-science package, not the sandbox. "
        f"Use `pydantic-monty`. Offending lines: {offenders}"
    )


def test_the_detector_can_actually_fail() -> None:
    """A checker that has never rejected anything is indistinguishable from `return []`.

    Both directions, because both are load-bearing: the trap must be caught, and the
    correct name must NOT be caught — a `_WRONG` pattern that also matched
    `pydantic-monty` would make the previous test fail on a correct file, which is the
    failure mode that gets a check deleted rather than fixed.
    """
    assert _WRONG.search('    "monty==2026.7.16",')
    assert _WRONG.search('    "monty>=1.0",')
    assert not _WRONG.search('    "pydantic-monty==0.0.19",')
    assert _CORRECT.search('    "pydantic-monty==0.0.19",')
    assert not _CORRECT.search('    "pydantic-monty>=0.0.19",')
