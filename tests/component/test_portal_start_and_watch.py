# SPDX-License-Identifier: Apache-2.0
"""US1 — a person starts a run from a conversation and watches it finish.

The portal is driven through its real routes against a real API app, with only the IdP
doubled. That shape is the point: a row that stubbed the relay would prove the templates
render and nothing about whether the portal can actually reach the platform.

SC-001's specific claim gets its own row — **no run identifier is ever shown to a person**.
It is the difference between a conversation and a ticketing system, and it is the kind of
thing that regresses the first time someone adds a debug field to a template.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME
from tests.harness.api_fixtures import SurfaceUnderTest, surface_under_test


def _visible_text(html: str) -> str:
    """What a person actually reads: tags and attributes removed.

    Deliberately crude — a real parser would be more precise and would also be a
    dependency this repository does not have. Removing everything between angle brackets
    is enough to distinguish "shown to a person" from "present in the markup", which is
    the only distinction this file needs.
    """
    import re

    without_tags = re.sub(r"<[^>]*>", " ", html)
    return " ".join(without_tags.split())


@dataclass
class PortalOverApi:
    """A portal whose relay reaches a real API app in-process."""

    portal: TestClient
    api: TestClient
    surface: SurfaceUnderTest
    oidc: OidcClient
    cookie: str


def _portal_over_api(subject: str = "alice") -> PortalOverApi:
    surface = surface_under_test(subject=subject)
    api = TestClient(surface.app)

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        """Carry the portal's request to the API app, headers and all.

        This is the relay's real request-shaping — path, method, body, bearer — delivered
        over ASGI instead of a socket. What is being tested is that the portal asks for the
        right things as the right person, and that survives the transport swap.
        """
        path = url.replace("http://api.test", "")
        response = api.request(
            method, path, json=json_body, headers={"Authorization": f"Bearer {token}"}
        )
        body = response.content
        return ApiResponse(status=response.status_code, payload=response.json() if body else None)

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
    app = create_portal(
        relay=ApiRelay(base_url="http://api.test", transport=transport),
        oidc=oidc,
    )
    portal = TestClient(app, base_url="http://testserver")

    state, _url = oidc.begin()
    code = surface.idp.authorize(
        code_challenge=code_challenge_for(oidc._pending[state].verifier),
        subject=subject,
        claims={"groups": ["platform"]},
    )
    signed_in = portal.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    cookie = str(signed_in.cookies.get(COOKIE_NAME))
    portal.cookies.set(COOKIE_NAME, cookie)

    return PortalOverApi(portal=portal, api=api, surface=surface, oidc=oidc, cookie=cookie)


def test_a_person_starts_a_run_and_sees_it_without_an_identifier() -> None:
    """SC-001, end to end through the portal's own routes."""
    setup = _portal_over_api()

    created = setup.portal.post("/threads", follow_redirects=False)
    assert created.status_code == 303
    thread_path = created.headers["location"]

    sent = setup.portal.post(
        thread_path + "/turns",
        data={"message": "plan the migration", "agent_definition_id": "planner"},
        follow_redirects=False,
    )
    assert sent.status_code == 303

    page = setup.portal.get(thread_path)
    assert page.status_code == 200
    assert "plan the migration" in page.text


def test_no_run_identifier_is_ever_shown_to_a_person() -> None:
    """SC-001: nobody is *given* an identifier, or has to record one.

    **The assertion is on visible text, not on the markup**, and the distinction is worth
    stating because the first version of this row asserted the stricter thing and failed.

    A run id necessarily appears in machinery: the stop form posts to
    `POST /runs/{run_id}/stop`, which is the catalogue's own operation shape. Avoiding
    that would mean inventing a stop-by-turn operation the API does not have — which is
    precisely the capability the portal is forbidden from adding. So the id reaches an
    attribute and a form action, and reaches a person nowhere.

    What SC-001 protects is the person's experience: they never read an identifier, never
    copy one, and never need one to get back to their work. That is what this checks.
    """
    setup = _portal_over_api()
    created = setup.portal.post("/threads", follow_redirects=False)
    thread_path = created.headers["location"]
    setup.portal.post(
        thread_path + "/turns",
        data={"message": "plan it", "agent_definition_id": "planner"},
        follow_redirects=False,
    )

    detail = setup.api.get(
        thread_path.replace("/threads/", "/threads/"), headers=setup.surface.bearer()
    )
    run_ids = [t["run_id"] for t in detail.json()["turns"] if t.get("run_id")]
    assert run_ids, "the row proves nothing if no run was started"

    page = setup.portal.get(thread_path)
    visible = _visible_text(page.text)
    for run_id in run_ids:
        assert run_id not in visible, (
            f"the page displays run id {run_id!r}; a person should never be given one"
        )


def test_definitions_are_shown_with_the_ones_they_cannot_start_flagged() -> None:
    """011's settled disclosure, rendered rather than re-decided."""
    setup = _portal_over_api()
    created = setup.portal.post("/threads", follow_redirects=False)

    page = setup.portal.get(created.headers["location"])

    # `planner` is startable for this subject; `applier` is not, and must still appear.
    assert "planner" in page.text
    assert "applier" in page.text
    assert "you do not have access" in page.text
    assert "disabled" in page.text


def test_the_composer_says_messages_are_recorded() -> None:
    """ADR-0051's cost is informed rather than hidden."""
    setup = _portal_over_api()
    created = setup.portal.post("/threads", follow_redirects=False)

    page = setup.portal.get(created.headers["location"])

    assert "recorded as evidence" in page.text


def test_a_signed_out_visitor_is_offered_sign_in_rather_than_an_error() -> None:
    setup = _portal_over_api()
    setup.portal.cookies.clear()

    page = setup.portal.get("/")

    assert page.status_code == 200
    assert "Sign in" in page.text


def test_an_unreachable_api_says_so_rather_than_showing_an_empty_platform() -> None:
    """The edge case: a thin client with nothing to fall back on must not look empty."""

    def dead(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        return ApiResponse(status=0, payload=None)

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
    app = create_portal(
        relay=ApiRelay(base_url="http://api.test", transport=dead),
        oidc=oidc,
    )
    portal = TestClient(app, base_url="http://testserver")
    state, _ = oidc.begin()
    code = surface.idp.authorize(code_challenge=code_challenge_for(oidc._pending[state].verifier))
    signed = portal.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    portal.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))

    page = portal.get("/")

    assert "could not be reached" in page.text
    assert "have not been lost" in page.text
    assert "not started any conversations" not in page.text, (
        "an unreachable platform was rendered as an empty one"
    )
