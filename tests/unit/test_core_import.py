# SPDX-License-Identifier: Apache-2.0
"""Smoke tests for the core package reservation (FR-002, FR-004)."""

from __future__ import annotations

import sys
from types import ModuleType


def test_import_core() -> None:
    import core

    assert isinstance(core, ModuleType)


def test_core_has_no_agent_framework_deps() -> None:
    """core must not pull agent frameworks into the import graph."""
    import core

    _ = core
    forbidden = {
        "pydantic_ai",
        "langgraph",
        "langchain",
        "langchain_core",
        "openai",
        "anthropic",
    }
    loaded = set(sys.modules)
    assert forbidden.isdisjoint(loaded), f"agent frameworks loaded: {forbidden & loaded}"


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
