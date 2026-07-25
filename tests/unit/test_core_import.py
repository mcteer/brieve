# SPDX-License-Identifier: Apache-2.0
"""Smoke tests for the core package reservation (FR-002, FR-004)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import ModuleType


def test_import_core() -> None:
    import core

    assert isinstance(core, ModuleType)


FORBIDDEN_FRAMEWORKS = (
    "pydantic_ai",
    "langgraph",
    "langchain",
    "langchain_core",
    "openai",
    "anthropic",
)


def test_core_has_no_agent_framework_deps() -> None:
    """core must not pull agent frameworks into the import graph (ADR-0001).

    Checked in a subprocess, not against this process's ``sys.modules``. Adapter
    tests legitimately import the framework, so an in-process check would pass or
    fail on test ordering rather than on the property — and a layering guard that
    depends on collection order is not a guard.
    """
    forbidden = ",".join(repr(name) for name in FORBIDDEN_FRAMEWORKS)
    program = (
        "import sys\n"
        "import core\n"
        "import core.run, core.tools.invoke, core.durability, core.approvals\n"
        f"forbidden = {{{forbidden}}}\n"
        "loaded = forbidden & set(sys.modules)\n"
        "print(','.join(sorted(loaded)))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", program],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[2],
    )
    leaked = proc.stdout.strip()
    assert not leaked, f"core pulled agent frameworks into its import graph: {leaked}"


def test_adapter_is_the_only_framework_importer() -> None:
    """Framework imports live under src/adapters, nowhere else in src/."""
    src = Path(__file__).resolve().parents[2] / "src"
    offenders = []
    for path in src.rglob("*.py"):
        if "adapters" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for name in FORBIDDEN_FRAMEWORKS:
            if f"import {name}" in text:
                offenders.append(f"{path.relative_to(src)}: {name}")
    assert not offenders, f"framework imported outside src/adapters: {offenders}"


def test_no_secret_like_strings_in_unit_fixtures() -> None:
    """Gate: unit tests must not embed credential-like literals."""
    from pathlib import Path

    # Patterns assembled so this test file does not contain the banned substrings.
    banned = (
        "BEGIN" + " PRIVATE KEY",
        "AK" + "IA",
        "pass" + "word=",
        "secret" + "_key=",
        "api" + "_key=",
    )
    roots = [Path("tests/unit"), Path("tests/harness")]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for token in banned:
                assert token not in text, f"{path} contains banned pattern"
