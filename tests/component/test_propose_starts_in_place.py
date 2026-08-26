# SPDX-License-Identifier: Apache-2.0
"""Starting a Build without losing the page — server envelope, not the browser half.

A full-page POST 303s to the run document, which is not how a chat interface behaves.
`portal-propose-submit.js` now posts the same form to the same endpoint and swaps in the run
column, and these rows hold the two properties that make that safe rather than merely nicer:

  * ONE RENDERER. The fragment and the full page both end at `_propose_run_main.html`, so the
    version somebody sees with JavaScript disabled cannot drift from the version everyone else
    sees.
  * THE FORM STILL WORKS WITHOUT THE SCRIPT. Progressive enhancement is only true if something
    checks it, so a request carrying no fragment header must still 303 to the run page.

The browser half — that the page does not navigate — belongs to `tests/a11y`, which drives a
real browser and is the only lane that can see it.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME
from tests.harness.api_fixtures import surface_under_test

_RUN_ID = "propose-in-place-test"
_MESSAGE = "Add a Vault cluster"


def _transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
    path = url.replace("http://api.test", "").split("?")[0]
    if method == "POST" and path == "/propose":
        return ApiResponse(status=200, payload={"run_id": _RUN_ID})
    if method == "GET" and path == "/runs":
        return ApiResponse(
            status=200,
            payload={
                "runs": [
                    {
                        "run_id": _RUN_ID,
                        "agent_definition_id": "authoring-agent",
                        "state": "running",
                    }
                ]
            },
        )
    if method == "GET" and path == f"/runs/{_RUN_ID}":
        return ApiResponse(status=200, payload={"state": "running"})
    if method == "GET" and path == f"/runs/{_RUN_ID}/result":
        return ApiResponse(status=200, payload={"intake_message": _MESSAGE})
    return ApiResponse(status=200, payload={})


def _portal() -> TestClient:
    """A signed-in portal whose relay always starts, so these rows test the ENVELOPE only."""
    surface = surface_under_test()
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
            relay=ApiRelay(base_url="http://api.test", transport=_transport),
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


def _post(portal: TestClient, *, fragment: bool, message: str = _MESSAGE) -> Any:
    headers = {"X-Portal-Fragment": "run"} if fragment else {}
    return portal.post("/", data={"message": message}, headers=headers, follow_redirects=False)


def test_the_fragment_carries_the_run_and_not_the_page() -> None:
    """What the script swaps in: the run column, with nothing wrapped around it."""
    body = _post(_portal(), fragment=True).text

    assert _MESSAGE in body
    assert 'data-propose-run="' + _RUN_ID + '"' in body
    assert 'id="phase-strip"' in body
    assert "<html" not in body.lower(), "the fragment carried a whole document"
    assert 'name="message"' not in body, "the fragment carried the composer it was posted from"
    assert "form.dock" not in body and 'class="dock"' not in body


def test_a_request_without_the_header_still_redirects_to_the_run_page() -> None:
    """The no-JavaScript path, which is the one nobody would notice breaking."""
    response = _post(_portal(), fragment=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"/propose/runs/{_RUN_ID}"


def test_both_envelopes_render_the_same_run_column() -> None:
    """ONE RENDERER, asserted rather than assumed.

    Two templates that agree today are two templates that drift, and the one that drifts is the
    one only reachable with JavaScript switched off — so nobody would see it happen.
    """
    portal = _portal()
    fragment = _post(portal, fragment=True).text.strip()
    page = portal.get(f"/propose/runs/{_RUN_ID}").text

    assert fragment in page, (
        "the fragment is not literally what the full page contains — the two have diverged"
    )


def test_a_refused_start_refuses_in_the_fragment_envelope() -> None:
    """A start the platform refused must not 303 a script into a whole error page."""
    surface = surface_under_test()

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        path = url.replace("http://api.test", "").split("?")[0]
        if method == "POST" and path == "/propose":
            return ApiResponse(status=400, payload={"detail": "Build could not be started"})
        return ApiResponse(status=200, payload={"runs": [], "conversations": []})

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
    portal = TestClient(
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
    signed = portal.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    portal.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))

    response = portal.post(
        "/",
        data={"message": _MESSAGE},
        headers={"X-Portal-Fragment": "run"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "could not be started" in response.text.lower()
    assert "<html" not in response.text.lower()


def test_the_build_page_offers_somewhere_for_a_run_to_land() -> None:
    """A regression here is silent: the form keeps working, just with a full-page navigation."""
    portal = _portal()
    home = portal.get("/").text
    assert "/static/portal-propose-submit.js" in home
    assert "dock" in home
    assert "data-create-home" in home

    run = portal.get(f"/propose/runs/{_RUN_ID}").text
    assert "/static/portal-propose.js" in run
    assert "/static/portal-propose-strip.js" in run
