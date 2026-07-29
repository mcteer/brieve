# SPDX-License-Identifier: Apache-2.0
"""US4 — stopping from a conversation is the API's stop, reached from a friendlier place.

FR-013: identical semantics, because it is the identical operation. The portal relays
`POST /runs/{run_id}/stop` with the person's own token and renders what comes back. There
is no thread-local stop, which is the contract's "two paths to one action" rule — and the
reason a row can assert equality rather than equivalence.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME
from tests.harness.api_fixtures import surface_under_test


def _portal_over_api() -> tuple[TestClient, TestClient, object]:
    surface = surface_under_test()
    api = TestClient(surface.app)
    seen: list[tuple[str, str]] = []

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        path = url.replace("http://api.test", "")
        seen.append((method, path))
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
    relay = ApiRelay(base_url="http://api.test", transport=transport)
    portal = TestClient(
        create_portal(relay=relay, oidc=oidc),
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
    portal.relay_log = seen  # type: ignore[attr-defined]
    return portal, api, surface


def _start_a_turn(portal: TestClient) -> tuple[str, str]:
    created = portal.post("/threads", follow_redirects=False)
    thread_path = created.headers["location"]
    portal.post(
        thread_path + "/turns",
        data={"message": "a long apply", "agent_definition_id": "planner"},
        follow_redirects=False,
    )
    return thread_path, thread_path.rsplit("/", 1)[-1]


def test_the_portal_stops_through_the_catalogues_own_operation() -> None:
    """No thread-local stop exists; the relay log proves which operation was used."""
    portal, api, surface = _portal_over_api()
    thread_path, thread_id = _start_a_turn(portal)

    detail = api.get(thread_path, headers=surface.bearer())  # type: ignore[attr-defined]
    run_id = detail.json()["turns"][0]["run_id"]

    portal.relay_log.clear()  # type: ignore[attr-defined]
    stopped = portal.post(
        f"/runs/{run_id}/stop", data={"thread_id": thread_id}, follow_redirects=False
    )

    assert stopped.status_code == 303
    calls = portal.relay_log  # type: ignore[attr-defined]
    assert ("POST", f"/runs/{run_id}/stop") in calls, (
        f"the portal did not use the catalogue's stop operation; it made {calls}"
    )


def test_stopping_from_the_portal_matches_stopping_through_the_api() -> None:
    """FR-013 as equality: same operation, so the same terminal state and reason."""
    portal, api, surface = _portal_over_api()
    thread_path, thread_id = _start_a_turn(portal)
    detail = api.get(thread_path, headers=surface.bearer())  # type: ignore[attr-defined]
    via_portal_run = detail.json()["turns"][0]["run_id"]

    portal.post(
        f"/runs/{via_portal_run}/stop", data={"thread_id": thread_id}, follow_redirects=False
    )
    from_portal = api.get(f"/runs/{via_portal_run}", headers=surface.bearer())  # type: ignore[attr-defined]

    started = api.post(
        "/runs",
        json={"agent_definition_id": "planner", "requested_tools": ["echo"]},
        headers=surface.bearer(),  # type: ignore[attr-defined]
    )
    direct_run = started.json()["run_id"]
    api.post(f"/runs/{direct_run}/stop", headers=surface.bearer())  # type: ignore[attr-defined]
    from_api = api.get(f"/runs/{direct_run}", headers=surface.bearer())  # type: ignore[attr-defined]

    assert from_portal.json()["state"] == from_api.json()["state"]
    assert from_portal.json().get("stop_reason") == from_api.json().get("stop_reason")


def test_a_turn_after_a_stop_is_a_new_run_not_a_resumption() -> None:
    """US4 scenario 3: consent to start is consent to finish, and this is a fresh start."""
    portal, api, surface = _portal_over_api()
    thread_path, thread_id = _start_a_turn(portal)
    detail = api.get(thread_path, headers=surface.bearer())  # type: ignore[attr-defined]
    first_run = detail.json()["turns"][0]["run_id"]
    portal.post(f"/runs/{first_run}/stop", data={"thread_id": thread_id}, follow_redirects=False)

    portal.post(
        thread_path + "/turns",
        data={"message": "try again", "agent_definition_id": "planner"},
        follow_redirects=False,
    )

    after = api.get(thread_path, headers=surface.bearer())  # type: ignore[attr-defined]
    runs = [t["run_id"] for t in after.json()["turns"] if t.get("run_id")]
    assert len(runs) == 2
    assert runs[1] != runs[0], "the second turn resumed the stopped run rather than starting one"


def test_the_portal_offers_no_stop_for_a_run_it_does_not_own() -> None:
    """Relaying is not authorizing: the API refuses and the portal renders the refusal."""
    portal, api, surface = _portal_over_api()
    _thread_path, thread_id = _start_a_turn(portal)

    refused = portal.post(
        "/runs/someone-elses-run/stop", data={"thread_id": thread_id}, follow_redirects=False
    )

    assert refused.status_code >= 400
    assert "did not" in refused.text
