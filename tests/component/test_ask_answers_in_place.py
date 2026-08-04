# SPDX-License-Identifier: Apache-2.0
"""Asking without losing the page — the server half, and the guarantees that keep it honest.

An answer takes a minute or two. Posting the whole page for it cost a person their scroll
position and left them on a blank tab with no sign anything was happening. `portal-ask.js` now
posts the same form to the same endpoint and swaps in the outcome, and these rows hold the two
properties that make that safe rather than merely nicer:

  * ONE RENDERER. The fragment and the full page both end at `_outcome.html`, so the version
    somebody sees with JavaScript disabled cannot drift from the version everyone else sees.
  * THE FORM STILL WORKS WITHOUT THE SCRIPT. Progressive enhancement is only true if something
    checks it, so a request carrying no fragment header must still get a whole page.

The browser half — that the page does not navigate, that focus lands on the answer — belongs to
`tests/a11y`, which drives a real browser and is the only lane that can see it.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME
from tests.harness.api_fixtures import surface_under_test

_ANSWER: dict[str, Any] = {
    "disposition": "answered",
    "source": "guidance",
    "ground_note": "Source material pinned today.",
    "claims": [
        {
            "statement": "A Vault cluster spans availability zones.",
            "citations": ["https://developer.hashicorp.com/patterns/vault/clustering#clustering"],
        }
    ],
}


@pytest.fixture
def portal() -> TestClient:
    """A signed-in portal whose relay always answers, so these rows test the ENVELOPE only."""
    surface = surface_under_test()

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        return ApiResponse(status=200, payload=_ANSWER)

    oidc = OidcClient(
        issuer=surface.idp.issuer,
        client_id="portal",
        redirect_uri="http://testserver/callback",
        authorize_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
        exchange=lambda code, code_verifier: surface.idp.exchange(
            code=code, code_verifier=code_verifier, redirect_uri="http://localhost/callback"
        ),
    )
    client = TestClient(
        create_portal(
            relay=ApiRelay(base_url="http://api.test", transport=transport),
            oidc=oidc,
        ),
        base_url="http://testserver",
    )
    state, _ = oidc.begin()
    code = surface.idp.authorize(
        code_challenge=code_challenge_for(oidc._pending[state].verifier),  # noqa: SLF001
        subject="alice",
        claims={"groups": ["platform"]},
    )
    signed = client.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    client.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))
    return client


def _post(portal: TestClient, *, fragment: bool, question: str = "Build a Vault cluster?") -> Any:
    headers = {"X-Portal-Fragment": "outcome"} if fragment else {}
    return portal.post("/ask", data={"question": question}, headers=headers)


def test_the_fragment_carries_the_answer_and_not_the_page(portal: TestClient) -> None:
    """What the script swaps in: the outcome, with nothing wrapped around it."""
    body = _post(portal, fragment=True).text

    assert "A Vault cluster spans availability zones." in body
    assert "<html" not in body.lower(), "the fragment carried a whole document"
    assert "<form" not in body.lower(), "the fragment carried the form it was posted from"
    assert "You asked" in body, "the fragment carried the answer without the question"


def test_a_request_without_the_header_still_gets_the_whole_page(portal: TestClient) -> None:
    """The no-JavaScript path, which is the one nobody would notice breaking."""
    body = _post(portal, fragment=False).text

    assert "A Vault cluster spans availability zones." in body
    assert "<html" in body.lower(), "the full-page path stopped returning a page"
    assert "<form" in body.lower(), "the full page came back without the form to ask again"


def test_both_envelopes_render_the_same_answer(portal: TestClient) -> None:
    """ONE RENDERER, asserted rather than assumed.

    Two templates that agree today are two templates that drift, and the one that drifts is the
    one only reachable with JavaScript switched off — so nobody would see it happen.
    """
    fragment = _post(portal, fragment=True).text.strip()
    page = _post(portal, fragment=False).text

    assert fragment in page, (
        "the fragment is not literally what the full page contains — the two have diverged"
    )


def test_an_empty_question_refuses_in_whichever_envelope_was_asked_for(portal: TestClient) -> None:
    """The cheapest refusal keeps its status and its words on both paths."""
    for fragment in (True, False):
        response = _post(portal, fragment=fragment, question="   ")

        assert response.status_code == 400
        assert "nothing was sent" in response.text.lower()


def test_the_ask_page_offers_somewhere_for_an_answer_to_land(portal: TestClient) -> None:
    """A regression here is silent: the form keeps working, just slowly and with a reload."""
    body = portal.get("/ask").text

    assert "/static/portal-ask.js" in body
    # `ask-outcome` became `ask-transcript` in 035: the region stopped being where THE answer
    # goes and became where EVERY answer accumulates. The name change is the behaviour change.
    assert 'id="ask-transcript"' in body, "there is nowhere for answers to accumulate"
    assert 'id="ask-status"' in body, "there is nothing to say the question is in flight"
