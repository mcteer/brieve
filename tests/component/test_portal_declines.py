# SPDX-License-Identifier: Apache-2.0
"""US5 — the surface says clearly when it has not done anything.

With answering split out, this story got *more* load-bearing rather than less. A portal
that only dispatches must be unmistakable when it has not dispatched, because there is no
answer arriving to signal that something happened — silence and success look identical.

The distinction the rows protect: a **decline** says the platform cannot do this; a
**refusal** says this person may not. Conflating them tells someone their access is fine
when it is not, and tells another it is broken when they simply have none.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME
from tests.harness.api_fixtures import surface_under_test


def _visible(html: str) -> str:
    return " ".join(re.sub(r"<[^>]*>", " ", html).split())


def _turns_only(html: str) -> str:
    """Just the conversation, without the composer beneath it.

    The composer lists every agent definition including the ones this person cannot start,
    each flagged "(you do not have access)" — 011's disclosure, rendered correctly. A row
    comparing whole pages would match that flag and conclude the decline and the refusal
    read the same, which is a defect in the row rather than in the page. Scoping to the
    turns is what makes the comparison about the dispositions.
    """
    body = html.split('<form method="post" action="/threads/')[0]
    return _visible(body)


def _portal_over_api() -> tuple[TestClient, TestClient, object]:
    surface = surface_under_test()
    api = TestClient(surface.app)

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        path = url.replace("http://api.test", "")
        response = api.request(
            method, path, json=json_body, headers={"Authorization": f"Bearer {token}"}
        )
        return ApiResponse(
            status=response.status_code,
            payload=response.json() if response.content else None,
        )

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
            secure_cookies=False,
        ),
        base_url="http://testserver",
    )
    state, _ = oidc.begin()
    code = surface.idp.authorize(
        code_challenge=code_challenge_for(oidc._pending[state].verifier),
        subject="alice",
        claims={"groups": ["platform"]},
    )
    signed = portal.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    portal.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))
    return portal, api, surface


def _send(portal: TestClient, thread_path: str, **data: str) -> None:
    portal.post(thread_path + "/turns", data=data, follow_redirects=False)


def test_a_decline_says_what_the_portal_is_for_without_looking_broken() -> None:
    portal, _api, _surface = _portal_over_api()
    thread_path = portal.post("/threads", follow_redirects=False).headers["location"]

    _send(portal, thread_path, message="what can you do?")
    page = _visible(portal.get(thread_path).text)

    assert "starts agents" in page
    assert "choose an agent" in page.lower()
    # Not an error, not a stack trace, not silence.
    assert "error" not in page.lower()


def test_a_scope_refusal_reads_differently_from_a_decline() -> None:
    """The distinction FR-017 protects, asserted on what a person actually reads."""
    portal, _api, _surface = _portal_over_api()

    declined_path = portal.post("/threads", follow_redirects=False).headers["location"]
    _send(portal, declined_path, message="nothing selected")
    declined = _turns_only(portal.get(declined_path).text)

    refused_path = portal.post("/threads", follow_redirects=False).headers["location"]
    _send(portal, refused_path, message="apply it", agent_definition_id="applier")
    refused = _turns_only(portal.get(refused_path).text)

    assert "do not have access" in refused
    assert "do not have access" not in declined
    assert declined != refused


def test_neither_a_decline_nor_a_refusal_starts_a_run() -> None:
    """FR-017a: a surface that dispatches on ambiguity is worse than one that declines."""
    portal, api, surface = _portal_over_api()

    declined_path = portal.post("/threads", follow_redirects=False).headers["location"]
    _send(portal, declined_path, message="nothing selected")
    refused_path = portal.post("/threads", follow_redirects=False).headers["location"]
    _send(portal, refused_path, message="apply it", agent_definition_id="applier")

    for path in (declined_path, refused_path):
        detail = api.get(path, headers=surface.bearer())  # type: ignore[attr-defined]
        assert all(t["run_id"] is None for t in detail.json()["turns"]), (
            "a decline or refusal started a run"
        )


def test_the_declined_message_is_still_shown_back_to_the_person() -> None:
    """They said something. The page should not pretend otherwise."""
    portal, _api, _surface = _portal_over_api()
    thread_path = portal.post("/threads", follow_redirects=False).headers["location"]

    _send(portal, thread_path, message="a thing the platform will not do")

    assert "a thing the platform will not do" in _visible(portal.get(thread_path).text)


def test_a_refusal_page_distinguishes_unreachable_from_forbidden() -> None:
    """The two must never render the same, because one is about access and one is not."""
    surface = surface_under_test()

    def dead(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        return ApiResponse(status=0, payload=None)

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
            relay=ApiRelay(base_url="http://api.test", transport=dead),
            oidc=oidc,
            secure_cookies=False,
        ),
        base_url="http://testserver",
    )
    state, _ = oidc.begin()
    code = surface.idp.authorize(code_challenge=code_challenge_for(oidc._pending[state].verifier))
    signed = portal.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    portal.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))

    page = _visible(portal.post("/threads", follow_redirects=False).text)

    assert "could not be reached" in page
    assert "not a permissions problem" in page
    assert "do not have access" not in page
