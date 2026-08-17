# SPDX-License-Identifier: Apache-2.0
"""047 — authoring-capable packs are discovered from manifests, not hardcoded."""

from __future__ import annotations

from pathlib import Path

from core.authoring.owned import packs_declaring_authoring


def test_packs_declaring_authoring_reads_workflow_names(tmp_path: Path) -> None:
    """A pack authors when a workflow name contains ``author``; others do not."""
    capable = tmp_path / "capable"
    capable.mkdir()
    (capable / "pack.toml").write_text(
        '[pack]\nname = "capable"\n\n[[workflows]]\nname = "author-module"\n'
        "minimum_tier = 2\npaved = false\n",
        encoding="utf-8",
    )
    other = tmp_path / "other"
    other.mkdir()
    (other / "pack.toml").write_text(
        '[pack]\nname = "other"\n\n[[workflows]]\nname = "review-configuration"\n'
        "minimum_tier = 1\npaved = true\n",
        encoding="utf-8",
    )
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "pack.toml").write_text("not toml {", encoding="utf-8")

    declared = packs_declaring_authoring(packs_root=tmp_path)
    assert declared == frozenset({"capable"})


def test_owned_module_does_not_name_a_managed_product() -> None:
    """The discovery helper must not hardcode a product the core is forbidden to know."""
    source = Path("src/core/authoring/owned.py").read_text(encoding="utf-8")
    assert "terraform" not in source
    assert "consul" not in source
    assert "packer" not in source
