# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — nothing anywhere resolves to a moving target (FR-011).

Auto-tracking does not arrive as a feature called auto-tracking. It arrives as an alias
somebody found convenient, a `latest` default that saved a config change, or a version
string with a wildcard in it. Each is small; each makes what ran on Tuesday different from
what was qualified on Monday, with nothing recording that anything changed.

**Asserted as an absence, with a positive control**, because an absence check nobody has
seen fire proves only that the search ran.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.matrix import MODEL_IDENTIFIER, parse_matrix_record

ROOT = Path(__file__).resolve().parents[3]

#: Shapes that resolve differently over time. `latest` and `*` are the obvious ones; a bare
#: `main` or `HEAD` is the same defect in a supply chain — content that changes without its
#: pin changing.
MOVING_TARGETS = re.compile(r"\b(latest|HEAD)\b|@\*|:\*|~>\s*\*")

#: Where a moving target would actually take effect: pack manifests pin content, and the
#: matrix pins models. Prose elsewhere may discuss "latest" freely — this file does.
PINNED_SURFACES = ("packs",)


def _pinning_files() -> list[Path]:
    return [p for base in PINNED_SURFACES for p in (ROOT / base).rglob("*.toml")]


def test_no_pack_manifest_pins_a_moving_target() -> None:
    offenders = {
        str(path.relative_to(ROOT)): MOVING_TARGETS.findall(path.read_text())
        for path in _pinning_files()
        if MOVING_TARGETS.search(path.read_text())
    }
    assert not offenders, (
        f"a manifest pins something that resolves differently over time: {offenders}. "
        f"Content that changes without its pin changing is the ungated drift Principle VIII "
        f"exists to stop"
    )


def test_every_adopted_skill_carries_a_concrete_commit() -> None:
    """A pin that is a branch name is not a pin.

    `commit = "main"` looks pinned and tracks. Asserting the shape — 40 hex characters —
    catches it where a "is `commit` present" check would not.
    """
    import tomllib

    for manifest_path in (ROOT / "packs").glob("*/pack.toml"):
        with manifest_path.open("rb") as handle:
            document = tomllib.load(handle)
        if document["pack"].get("provenance") != "adopted":
            continue
        commit = document.get("upstream", {}).get("commit", "")
        assert re.fullmatch(r"[0-9a-f]{40}", commit), (
            f"{manifest_path.relative_to(ROOT)} pins commit {commit!r}, which is not a "
            f"concrete revision; a branch name looks pinned and tracks"
        )


@pytest.mark.parametrize("model", ["latest", "anthropic/claude", "*", "claude@5"])
def test_the_matrix_cannot_express_an_unpinned_model(model: str) -> None:
    """Caught at the identifier, so a matrix cannot auto-track even by accident.

    `anthropic/latest@1` is deliberately NOT in this list: it satisfies
    provider/model@version and the pattern cannot tell a version from a word. That limit is
    asserted as its own row in `test_matrix_reader.py` rather than hidden by omitting the
    case here — a floor nobody has seen the shape of gets read as a ceiling.
    """
    record = {
        "schema_version": 1,
        "cells": [{"pack": "vault", "model": model, "role": "write", "qualified_by": "fixture"}],
    }
    with pytest.raises(ResolutionRefused):
        parse_matrix_record(record)


def test_no_source_module_defaults_a_model_or_version_to_latest() -> None:
    """The other direction: not what a record says, but what code would substitute.

    A default of `"latest"` in code is auto-tracking that no record shows, because the
    record simply omits the field.

    Only `latest`, deliberately. A first draft also matched `HEAD` and `*` and caught
    `src/surfaces/api/app.py` — where `HEAD` is the **HTTP method**. A check that flags
    correct code teaches people to widen its exemptions, which is how it stops catching
    anything. Git refs and globs belong to manifests, and the manifest check above covers
    them.
    """
    offenders: dict[str, list[str]] = {}
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        hits = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and node.value.strip().lower() == "latest"
        ]
        if hits:
            offenders[str(path.relative_to(ROOT))] = hits
    assert not offenders, f"a module defaults to a moving target: {offenders}"


def test_the_check_fires_on_a_contrived_violation(tmp_path: Path) -> None:
    """The positive control, for both halves."""
    manifest = tmp_path / "pack.toml"
    manifest.write_text('[upstream]\ncommit = "latest"\n')
    assert MOVING_TARGETS.search(manifest.read_text())

    assert not MODEL_IDENTIFIER.match("anthropic/claude")
    assert MODEL_IDENTIFIER.match("anthropic/claude-opus@5")
