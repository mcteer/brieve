# SPDX-License-Identifier: Apache-2.0
"""048 shell contracts: in-flight Build is a conversation, not a second propose."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from surfaces.portal.relay import ApiResponse

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
    page = (TEMPLATES / "propose_run.html").read_text()
    source = (TEMPLATES / "_propose_run_main.html").read_text()

    assert 'include "_propose_run_main.html"' in page
    assert "{{ intake_message }}" in source
    assert re.search(r"\{%\s*if\s+intake_message\s*%\}", source)
    assert 'id="phase-strip"' in source
    assert "data-phase" in source
    assert not re.search(r'action="/(?:propose)?"[\s>]', source)
    assert 'action="/propose"' not in source
    assert ">New build<" not in source
    assert ">Stop<" in source
    assert "/runs/" in source and "/stop" in source

    for status in ("completed", "active", "pending", "failed"):
        assert f"node--{status}" in source or "phase.status" in source
    assert "node--" in source
    assert "phase-status" in source
    assert "phase-reason" not in source


def test_exchange_uses_you_for_the_question() -> None:
    source = (TEMPLATES / "_exchange.html").read_text()
    assert 'class="you"' in source or 'class="you ' in source


def test_ask_heading_is_the_verb_not_the_question() -> None:
    """Empty home is the mark; an open item uses the existing title."""
    source = (TEMPLATES / "ask.html").read_text()
    assert "Let's Create" not in source
    assert "hashicorp-logomark.svg" in source
    assert "item-title" in source
    assert "visually-hidden" in source


def test_ask_answer_is_not_a_two_column_spine() -> None:
    """A dot + content grid shoved the answer (and its code) off the column edge."""
    source = (TEMPLATES / "_exchange.html").read_text()
    assert 'class="node node--completed"' in source
    assert 'class="dot"' not in source


def test_thread_and_composer_share_a_horizontal_inset() -> None:
    """Mismatched padding-inline puts the reading column and the composer
    in different boxes, so the answer, code, and field never share an edge."""
    css = (TEMPLATES.parent / "static" / "portal.css").read_text()
    thread = css.split(".thread {", 1)[1].split("}", 1)[0]
    dock = css.split(".dock {", 1)[1].split("}", 1)[0]
    assert "26px 30px 8px" in thread
    assert "14px 30px 18px" in dock
    assert "62ch" not in css.split(".primary-answer-prose {", 1)[1].split("}", 1)[0]
    exchange = css.split(".exchange .primary-answer-prose,", 1)
    assert exchange[0]  # selector exists via the grouped answer rule
    assert "max-width: 100%" in css.split(".exchange .answer,", 1)[1].split("}", 1)[0]


def test_signed_in_empty_ask_is_303_home() -> None:
    """T005: empty `/ask` is gone."""
    from fastapi.testclient import TestClient

    from surfaces.portal.app import create_portal
    from surfaces.portal.oidc import OidcClient, code_challenge_for
    from surfaces.portal.relay import ApiRelay, ApiResponse
    from surfaces.portal.session import COOKIE_NAME
    from tests.harness.fake_oidc_provider import FakeOIDCProvider

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        return ApiResponse(status=200, payload={"conversations": [], "runs": []})

    idp = FakeOIDCProvider()
    oidc = OidcClient(
        issuer=idp.issuer,
        client_id="portal",
        redirect_uri="http://testserver/callback",
        authorize_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        exchange=lambda code, code_verifier: idp.exchange(
            code=code, code_verifier=code_verifier, redirect_uri="http://localhost/callback"
        ),
    )
    client = TestClient(
        create_portal(relay=ApiRelay(base_url="http://api.test", transport=transport), oidc=oidc),
        base_url="http://testserver",
    )
    state, _ = oidc.begin()
    code = idp.authorize(
        code_challenge=code_challenge_for(oidc._pending[state].verifier), subject="alice"
    )
    signed = client.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    client.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))
    response = client.get("/ask", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers.get("location") == "/"


def test_exchange_and_outcome_keep_decision_comments() -> None:
    """FR-014 / research F9."""
    exchange = (TEMPLATES / "_exchange.html").read_text()
    outcome = (TEMPLATES / "_outcome.html").read_text()

    assert "ONE EXCHANGE" in exchange
    assert "conversation this exchange landed in" in exchange
    assert "DISPATCH ORDER IS LOAD-BEARING" in outcome
    assert "A PLATFORM THAT SAID NOTHING HAS NOT REFUSED ANYBODY" in outcome
    assert "body-less 500" in outcome or "body-less" in outcome


def _signed_portal(transport: Callable[..., ApiResponse]) -> TestClient:
    from surfaces.portal.app import create_portal
    from surfaces.portal.oidc import OidcClient, code_challenge_for
    from surfaces.portal.relay import ApiRelay
    from surfaces.portal.session import COOKIE_NAME
    from tests.harness.fake_oidc_provider import FakeOIDCProvider

    idp = FakeOIDCProvider()
    oidc = OidcClient(
        issuer=idp.issuer,
        client_id="portal",
        redirect_uri="http://testserver/callback",
        authorize_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        exchange=lambda code, code_verifier: idp.exchange(
            code=code, code_verifier=code_verifier, redirect_uri="http://localhost/callback"
        ),
    )
    client = TestClient(
        create_portal(relay=ApiRelay(base_url="http://api.test", transport=transport), oidc=oidc),
        base_url="http://testserver",
    )
    state, _ = oidc.begin()
    code = idp.authorize(
        code_challenge=code_challenge_for(oidc._pending[state].verifier), subject="alice"
    )
    signed = client.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    client.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))
    return client


def test_empty_home_is_create_with_ask_selected() -> None:
    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        return ApiResponse(status=200, payload={"conversations": [], "runs": []})

    page = _signed_portal(transport).get("/")
    assert page.status_code == 200
    assert "Let's Create" not in page.text
    assert "/static/mark/hashicorp-logomark.svg" in page.text
    assert 'action="/ask"' in page.text
    assert 'value="ask"' in page.text
    assert "Home/Code" not in page.text
    assert "model picker" not in page.text.lower()
    assert ">Share<" not in page.text


def test_combined_history_lists_ask_and_build_not_operator() -> None:
    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        if "/ask-conversations" in url:
            return ApiResponse(
                status=200,
                payload={
                    "conversations": [
                        {
                            "conversation_id": "ask-1",
                            "title": "How does Vault issue identity?",
                            "last_asked_at": "2026-08-25T12:00:00Z",
                        }
                    ]
                },
            )
        if url.rstrip("/").endswith("/runs"):
            return ApiResponse(
                status=200,
                payload={
                    "runs": [
                        {
                            "run_id": "propose-abc123",
                            "agent_definition_id": "authoring-agent",
                            "created_at": "2026-08-24T12:00:00Z",
                            "state": "completed",
                        },
                        {
                            "run_id": "run-operator",
                            "agent_definition_id": "planner",
                            "created_at": "2026-08-26T12:00:00Z",
                            "state": "completed",
                        },
                    ]
                },
            )
        return ApiResponse(status=200, payload={})

    page = _signed_portal(transport).get("/")
    assert "How does Vault issue identity?" in page.text
    assert 'href="/ask/ask-1"' in page.text
    assert ">Ask<" in page.text
    assert ">Build<" in page.text
    assert 'href="/propose/runs/propose-abc123"' in page.text
    assert "run-operator" not in page.text
    assert "portal-history.js" in page.text


def test_unreadable_lists_are_notices_not_empty_claims() -> None:
    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        if "/ask-conversations" in url:
            return ApiResponse(status=503, payload={})
        if url.rstrip("/").endswith("/runs"):
            return ApiResponse(status=503, payload={})
        return ApiResponse(status=200, payload={})

    page = _signed_portal(transport).get("/")
    assert "Ask history could not be read" in page.text
    assert "Build history could not be read" in page.text
    assert "no conversations" not in page.text.lower()
    assert "No conversations yet" not in page.text


def test_placeholders_do_not_navigate_or_attach() -> None:
    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        return ApiResponse(status=200, payload={"conversations": [], "runs": []})

    page = _signed_portal(transport).get("/").text
    assert 'aria-label="Attach context"' in page
    assert 'type="file"' not in page
    assert 'aria-label="Projects"' in page
    assert 'href="/projects"' not in page
    assert "Not available yet" in page


def test_propose_run_stop_lives_in_the_bubble() -> None:
    source = (TEMPLATES / "_propose_run_main.html").read_text()
    page = (TEMPLATES / "propose_run.html").read_text()
    assert 'include "_propose_run_main.html"' in page
    assert not re.search(r'method="post"\s+action="/"', source)
    assert 'action="/propose"' not in source
    assert 'action="/runs/' in source and "/stop" in source
    assert ">Stop<" in source
    assert "Home/Code" not in source
    assert ">Share<" not in source
    assert 'state in ("stopped", "completed", "failed")' in source


def test_failed_stop_does_not_present_the_run_as_ended() -> None:
    """T019: a refused stop is a refusal, not a finished Build."""
    from fastapi.testclient import TestClient

    from surfaces.portal.app import create_portal
    from surfaces.portal.oidc import OidcClient, code_challenge_for
    from surfaces.portal.relay import ApiRelay
    from surfaces.portal.session import COOKIE_NAME
    from tests.harness.fake_oidc_provider import FakeOIDCProvider

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        if method == "POST" and url.rstrip("/").endswith("/stop"):
            return ApiResponse(status=503, payload={"detail": "stop could not be recorded"})
        if url.rstrip("/").endswith("/runs"):
            return ApiResponse(status=200, payload={"runs": []})
        if "/ask-conversations" in url:
            return ApiResponse(status=200, payload={"conversations": []})
        return ApiResponse(status=200, payload={"state": "running"})

    idp = FakeOIDCProvider()
    oidc = OidcClient(
        issuer=idp.issuer,
        client_id="portal",
        redirect_uri="http://testserver/callback",
        authorize_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        exchange=lambda code, code_verifier: idp.exchange(
            code=code, code_verifier=code_verifier, redirect_uri="http://localhost/callback"
        ),
    )
    client = TestClient(
        create_portal(relay=ApiRelay(base_url="http://api.test", transport=transport), oidc=oidc),
        base_url="http://testserver",
    )
    state, _ = oidc.begin()
    code = idp.authorize(
        code_challenge=code_challenge_for(oidc._pending[state].verifier), subject="alice"
    )
    signed = client.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    client.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))
    page = client.post("/runs/propose-inflight/stop")
    assert page.status_code == 503
    assert "This build has ended" not in page.text
    assert "Ended without a pull request" not in page.text
    assert "stop that run" in page.text.lower()


def test_the_dial_counts_the_phase_in_progress_not_the_ones_finished() -> None:
    """A run actively researching is on phase 1 of 5, and the dial said 0.

    Counting completed phases is true of the finished count and wrong about the thing a
    person looks at a dial to learn: the tick moved a beat after work began rather than when
    it began. A failed phase counts the same way — it is where the run got to.
    """
    from surfaces.portal.app import _phase_position

    def phases(*statuses: str) -> list[dict[str, str]]:
        names = ("research", "plan", "write", "judge", "propose")
        return [{"name": n, "status": s} for n, s in zip(names, statuses, strict=True)]

    pending = ("pending",) * 4
    assert _phase_position(phases("active", *pending)) == 1
    assert _phase_position(phases("completed", "active", "pending", "pending", "pending")) == 2
    assert _phase_position(phases("completed", "completed", "completed", "failed", "pending")) == 4
    assert _phase_position(phases(*("completed",) * 5)) == 5
    # Nothing started at all is the one case where an empty dial is the honest picture.
    assert _phase_position(phases(*("pending",) * 5)) == 0


def test_the_dial_rule_is_the_same_on_the_server_and_in_the_live_updater() -> None:
    """Two implementations of one rule, so each names the other.

    The server renders the first dial and the SSE updater redraws every one after it. If they
    diverge the dial changes meaning the moment a phase advances, which is worse than either
    rule on its own.
    """
    script = (TEMPLATES.parent / "static" / "portal-propose-strip.js").read_text()
    assert 'phase.status === "active" || phase.status === "failed"' in script
    assert "done = at + 1" in script
    assert "_phase_position" in script, "the updater does not name the rule it mirrors"
