# SPDX-License-Identifier: Apache-2.0
"""P7 — Build portal is one chat bubble; no agent picker (047)."""

from __future__ import annotations

from pathlib import Path

from surfaces.portal.app import _build_rail_title


def test_build_rail_title_strips_the_propose_prefix() -> None:
    assert _build_rail_title("propose-7a135d72e1cea0e2") == "7a135d72e1cea0e2"


def test_p7_propose_template_has_no_agent_select() -> None:
    root = Path(__file__).resolve().parents[3]
    html = (root / "src/surfaces/portal/templates/propose.html").read_text(encoding="utf-8")
    assert "<select" not in html
    assert "agent_definition" not in html
    assert 'name="message"' in html
    assert 'name="repository"' not in html
    assert 'name="task"' not in html
    assert ">Build<" in html
    assert ">Send<" not in html
    assert 'class="composer"' in html
    assert 'include "_build_rail.html"' in html


def test_p7_run_page_shares_the_build_rail() -> None:
    root = Path(__file__).resolve().parents[3]
    html = (root / "src/surfaces/portal/templates/propose_run.html").read_text(encoding="utf-8")
    assert 'include "_build_rail.html"' in html
    assert "main--app" in html


def test_p7_base_nav_links_build_home_and_ask() -> None:
    root = Path(__file__).resolve().parents[3]
    base = (root / "src/surfaces/portal/templates/base.html").read_text(encoding="utf-8")
    assert 'href="/"' in base
    assert ">Build<" in base
    assert 'href="/ask"' in base
    assert ">Ask<" in base
    assert "Ask a question" not in base
    assert "Run an agent" not in base


def test_p8_ask_has_no_propose_control() -> None:
    """Ask cannot open a PR (047 P8) — no posting control to Build from the Ask page."""
    root = Path(__file__).resolve().parents[3]
    html = (root / "src/surfaces/portal/templates/ask.html").read_text(encoding="utf-8")
    assert 'action="/ask' in html
    assert 'action="/"' not in html
    assert 'action="/propose"' not in html
    assert 'name="message"' not in html
