# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — practice is product-specific (049, T035). Substring only."""

from __future__ import annotations

from pathlib import Path

PACKS = Path(__file__).resolve().parents[3] / "packs"


def test_terraform_write_names_terraform_authoring_constraints() -> None:
    body = (PACKS / "terraform" / "agents" / "write" / "AGENTS.md").read_text(encoding="utf-8")
    for needle in ("modules", "state", "variables", "secret"):
        assert needle.lower() in body.lower(), needle
    assert "terraform.tfstate" in body or "remote state" in body.lower()


def test_vault_write_does_not_instruct_terraform_resources() -> None:
    body = (PACKS / "vault" / "agents" / "write" / "AGENTS.md").read_text(encoding="utf-8")
    assert "aws_instance" in body  # named as an anti-pattern, not as the change
    assert "Do not emit" in body or "do not emit" in body.lower()
    assert "least privilege" in body.lower() or "least-privilege" in body.lower()
    assert "ACL" in body or "polic" in body.lower()
