# SPDX-License-Identifier: Apache-2.0
"""048 shell contracts: in-flight Build is a conversation, not a second propose."""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "surfaces" / "portal" / "templates"


def test_html_pages_are_not_cached() -> None:
    """A refresh of Ask was serving the previous document, so layout fixes never appeared."""
    from fastapi.testclient import TestClient

    from surfaces.portal.app import create_portal
    from surfaces.portal.oidc import OidcClient
    from surfaces.portal.relay import ApiRelay, ApiResponse

    portal = create_portal(
        relay=ApiRelay(
            base_url="http://api.test",
            transport=lambda **kwargs: ApiResponse(status=200, payload={}),
        ),
        oidc=OidcClient(
            issuer="http://idp.test",
            client_id="portal",
            redirect_uri="http://localhost/callback",
            authorize_endpoint="http://idp.test/authorize",
            token_endpoint="http://idp.test/token",
            exchange=lambda code, code_verifier: {},
        ),
    )
    response = TestClient(portal).get("/")
    assert "text/html" in response.headers.get("content-type", "")
    assert response.headers.get("cache-control") == "no-store"


def test_propose_run_shows_intake_only_from_the_field() -> None:
    source = (TEMPLATES / "propose_run.html").read_text()

    assert "{{ intake_message }}" in source
    assert re.search(r"\{%\s*if\s+intake_message\s*%\}", source)
    assert 'id="phase-strip"' in source
    assert "data-phase" in source
    assert 'method="post"' not in source.lower() or (
        'action="/"' not in source and 'action="/propose"' not in source
    )
    assert 'action="/"' not in source
    assert 'action="/propose"' not in source
    assert 'aria-label="New build"' in source or ">New build<" in source

    for status in ("completed", "active", "pending", "failed"):
        assert f"node--{status}" in source or "phase.status" in source
    assert "node--" in source
    assert "phase-status" in source
    assert "phase-reason" not in source


def test_exchange_uses_you_for_the_question() -> None:
    source = (TEMPLATES / "_exchange.html").read_text()
    assert 'class="you"' in source or 'class="you ' in source


def test_ask_heading_is_the_verb_not_the_question() -> None:
    """The bubble is the question. Repeating it as the page title sat beside the bubble."""
    source = (TEMPLATES / "ask.html").read_text()
    assert ">Ask</h1>" in source
    assert "title or" not in source
    assert "visually-hidden" in source


def test_ask_answer_is_not_a_two_column_spine() -> None:
    """A dot + content grid shoved the answer (and its code) off the column edge."""
    source = (TEMPLATES / "_exchange.html").read_text()
    assert 'class="node node--completed"' in source
    assert 'class="dot"' not in source


def test_thread_and_composer_share_a_horizontal_inset() -> None:
    """Mismatched padding-inline centers the 680px column and the 880px composer
    in different boxes, so the answer, code, and field never share an edge."""
    css = (TEMPLATES.parent / "static" / "portal.css").read_text()
    thread = css.split(".thread {", 1)[1].split("}", 1)[0]
    dock = css.split(".ask,\n.dock {", 1)[1].split("}", 1)[0]
    assert "28px 28px 20px" in thread
    assert "12px 28px 16px" in dock
    assert "62ch" not in css.split(".primary-answer-prose {", 1)[1].split("}", 1)[0]
    exchange = css.split(".exchange .primary-answer-prose,", 1)
    assert exchange[0]  # selector exists via the grouped answer rule
    assert "max-width: 100%" in css.split(".exchange .answer,", 1)[1].split("}", 1)[0]


def test_exchange_and_outcome_keep_decision_comments() -> None:
    """FR-014 / research F9."""
    exchange = (TEMPLATES / "_exchange.html").read_text()
    outcome = (TEMPLATES / "_outcome.html").read_text()

    assert "ONE EXCHANGE" in exchange
    assert "conversation this exchange landed in" in exchange
    assert "DISPATCH ORDER IS LOAD-BEARING" in outcome
    assert "A PLATFORM THAT SAID NOTHING HAS NOT REFUSED ANYBODY" in outcome
    assert "body-less 500" in outcome or "body-less" in outcome
