# SPDX-License-Identifier: Apache-2.0
"""P7 — Propose composer has no agent picker (047)."""

from __future__ import annotations

from pathlib import Path


def test_p7_propose_template_has_no_agent_select() -> None:
    root = Path(__file__).resolve().parents[3]
    html = (root / "src/surfaces/portal/templates/propose.html").read_text(encoding="utf-8")
    assert 'name="agent_definition_id"' not in html
    assert "<select" not in html
    assert 'name="repository"' in html
    assert 'name="task"' in html


def test_p7_base_nav_links_propose_and_ask() -> None:
    root = Path(__file__).resolve().parents[3]
    base = (root / "src/surfaces/portal/templates/base.html").read_text(encoding="utf-8")
    assert 'href="/propose"' in base
    assert 'href="/ask"' in base
