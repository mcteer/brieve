# SPDX-License-Identifier: Apache-2.0
"""The provenance check reports drift and adopts nothing — and refuses what is ours.

**The row that would have caught the planning error** (analyze C1): the first row here
asserts that the record consumed is the loader's own `[upstream]` pin. The draft plan
proposed adding a second provenance table; two records drift apart exactly when a bump
happens, and this row is where a future draft meets that argument.

**The row with teeth** is the drift one: after a run that finds upstream moved, every byte
of the pack — skills content, digests, the recorded commit — is unchanged. A weekly script
that quietly vendored new third-party instructions into an agent's skill set would be the
supply-chain failure the pack mechanism exists to prevent, wearing automation's clothes.
"""

from __future__ import annotations

import importlib.util
import shutil
import tomllib
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
TODAY = "2026-08-03"


def _module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "skills_provenance_under_test", ROOT / "infra" / "bin" / "skills_provenance.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pack_copy(tmp_path: Path, name: str) -> Path:
    """A real pack, copied — so these rows exercise the manifests that actually ship."""
    destination = tmp_path / name
    shutil.copytree(ROOT / "packs" / name, destination)
    return destination / "pack.toml"


def test_the_record_consumed_is_the_loaders_own_upstream_pin() -> None:
    """C1's row. `UpstreamPin` is required for adopted packs (ADR-0004) and already carries
    everything a drift check needs; a second provenance table would be a second truth."""
    from core.packs.loader import parse_manifest

    raw = tomllib.loads((ROOT / "packs" / "terraform" / "pack.toml").read_text())
    manifest = parse_manifest(raw)

    assert manifest.upstream is not None
    assert manifest.upstream.repository
    assert manifest.upstream.commit
    assert manifest.upstream.retrieved

    assert "upstream" in raw, "the pin the check consumes is the one the loader parses"
    assert "skills" in raw, (
        "the [[skills]] array of tables is what a `[skills.provenance]` table would have "
        "collided with — the shape error the analysis pass caught before it shipped"
    )


def test_an_unchanged_upstream_moves_only_the_retrieved_line(tmp_path: Path) -> None:
    """The clean-check case — and the I3 row: comments survive, because the edit is one line
    rather than a re-serialization."""
    module = _module()
    manifest = _pack_copy(tmp_path, "terraform")
    recorded = tomllib.loads(manifest.read_text())["upstream"]["commit"]
    module._upstream_head = lambda repository: recorded
    before = manifest.read_text()

    line, moved = module.check_pack(manifest, today=TODAY)

    assert moved is False
    assert "unchanged" in line

    # Asserted as an OUTCOME rather than as "exactly one line differs", because the committed
    # manifest's `retrieved` moves whenever a real check runs — and a row that assumed it
    # differed from TODAY failed the first time the two coincided. Binding a property to a
    # mutable artifact is the same mistake the corpus row made, one file over.
    after = manifest.read_text()
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    assert len(before_lines) == len(after_lines), "the line count changed — this is not an edit"
    for index, (was, now) in enumerate(zip(before_lines, after_lines, strict=True)):
        if now.strip().startswith("retrieved"):
            assert now.strip() == f'retrieved  = "{TODAY}"', "the retrieved line is not today's"
        else:
            assert was == now, f"line {index + 1} moved and should not have: {was!r} → {now!r}"
    assert "# Transport is MCP because a mature server exists" in after, (
        "the manifest's comments did not survive — a TOML re-serialization erased the reasoning "
        "that makes this file reviewable"
    )


def test_a_repository_that_moved_without_touching_our_skills_is_not_news(tmp_path: Path) -> None:
    """**The row the first real run earned.** The first implementation compared repository HEAD
    and reported UPSTREAM MOVED against hashicorp/agent-skills — for a README commit about npx
    installation, in a plugin this platform does not vendor. The skill actually adopted here was
    untouched, and the maintainer caught the false alarm before the proposal was believed.

    A weekly report that cries wolf is worse than no report: it trains the reviewer to skim past
    the week it matters. So drift means OUR content moved, and a repository that moved without
    touching it says so plainly.
    """
    module = _module()
    manifest = _pack_copy(tmp_path, "terraform")
    module._upstream_head = lambda repository: "f" * 40
    module._paths_changed_between = lambda repository, old, new, paths: []

    line, moved = module.check_pack(manifest, today=TODAY)

    assert moved is False, "an unrelated upstream commit was reported as something to review"
    assert "NOT the skills we vendored" in line
    assert "nothing to review" in line


def test_the_check_is_scoped_to_the_paths_the_pack_declares(tmp_path: Path) -> None:
    """Scoped from the pack's own `[[skills]]` entries — not a list maintained beside them,
    which would drift from what is actually vendored exactly when a skill was added."""
    module = _module()
    manifest = _pack_copy(tmp_path, "terraform")
    module._upstream_head = lambda repository: "f" * 40
    seen: list[list[str]] = []

    def _record(repository: str, old: str, new: str, paths: list[str]) -> list[str]:
        seen.append(list(paths))
        return []

    module._paths_changed_between = _record
    module.check_pack(manifest, today=TODAY)

    assert seen, "the check never scoped to a path"
    assert any("terraform-style-guide" in pattern for pattern in seen[0]), (
        f"the check did not scope to the vendored skill: {seen[0]}"
    )


def test_drift_in_our_own_content_is_reported_and_nothing_is_vendored(tmp_path: Path) -> None:
    """The row with teeth. Our skill moved; the pack is byte-identical afterwards."""
    module = _module()
    pack_dir = tmp_path / "terraform"
    manifest = _pack_copy(tmp_path, "terraform")
    module._upstream_head = lambda repository: "f" * 40
    module._paths_changed_between = lambda repository, old, new, paths: [
        "terraform/code-generation/skills/terraform-style-guide/SKILL.md"
    ]

    before = {
        path.relative_to(pack_dir): path.read_bytes()
        for path in sorted(pack_dir.rglob("*"))
        if path.is_file()
    }

    line, moved = module.check_pack(manifest, today=TODAY)

    assert moved is True
    assert "OUR VENDORED CONTENT MOVED" in line
    assert "SKILL.md" in line, "the report does not name what changed"
    assert "Nothing was vendored" in line
    assert "reviewed act" in line, "the report must point at the promotion path, not just a diff"

    after = {
        path.relative_to(pack_dir): path.read_bytes()
        for path in sorted(pack_dir.rglob("*"))
        if path.is_file()
    }
    assert after == before, "a drift check changed the pack — content adoption must stay human"


def test_an_authored_pack_is_refused_by_the_field_the_loader_enforces(tmp_path: Path) -> None:
    """F7. `vault-secret-access` was written here and is intended as an upstream PR; a
    'refresh' from a name-colliding upstream would overwrite our own authorship."""
    module = _module()
    manifest = _pack_copy(tmp_path, "vault")

    def _must_not_be_called(repository: str) -> str:
        raise AssertionError("an authored pack reached the network")

    module._upstream_head = _must_not_be_called
    module._paths_changed_between = _must_not_be_called
    before = manifest.read_text()

    line, moved = module.check_pack(manifest, today=TODAY)

    assert moved is False
    assert "authored here" in line
    assert "not checked" in line
    assert manifest.read_text() == before, "an authored pack's manifest was rewritten"


def test_an_adopted_pack_with_no_pin_fails_loudly(tmp_path: Path) -> None:
    """The loader already refuses this manifest; the check refuses it the same way rather
    than silently treating a missing pin as 'nothing to compare'."""
    module = _module()
    manifest = _pack_copy(tmp_path, "terraform")
    text = manifest.read_text()
    start = text.index("[upstream]")
    end = text.index("[[tools]]")
    manifest.write_text(text[:start] + text[end:])

    with pytest.raises(RuntimeError, match="no \\[upstream\\] pin"):
        module.check_pack(manifest, today=TODAY)
