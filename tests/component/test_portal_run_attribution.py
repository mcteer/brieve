# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — SC-007: a portal-started run is indistinguishable from an API one.

The claim is stronger than "equivalent". The portal relays the person's own token to the
same operation, so the API sees the person and starts the run the same way it always does.
There is no portal code path in the run's history at all — which is why the trail cannot
tell, and why nothing about a run's provenance needs to be checked at read time.

If this ever fails, the portal has acquired an identity of its own, and every downstream
guarantee about *who did this* is about the wrong party.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.audit.schema import AuditEventType
from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME
from tests.harness.api_fixtures import surface_under_test


def _portal_and_api(subject: str = "alice") -> tuple[TestClient, TestClient, object]:
    surface = surface_under_test(subject=subject)
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
        subject=subject,
        claims={"groups": ["platform"]},
    )
    signed = portal.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    portal.cookies.set(COOKIE_NAME, str(signed.cookies.get(COOKIE_NAME)))
    return portal, api, surface


def _event_shapes(surface: object, correlation_id: str) -> list[tuple[str, str]]:
    """(event type, subject) for a correlation id — what the trail says happened."""
    return [
        (str(e.event_type), str(e.payload.get("subject_user_id", "")))
        for e in surface.audit.list_by_correlation_id(correlation_id)  # type: ignore[attr-defined]
    ]


def test_a_portal_started_run_names_the_person_not_the_portal() -> None:
    portal, api, surface = _portal_and_api()
    created = portal.post("/threads", follow_redirects=False)
    thread_path = created.headers["location"]

    portal.post(
        thread_path + "/turns",
        data={"message": "plan it", "agent_definition_id": "planner"},
        follow_redirects=False,
    )

    detail = api.get(thread_path, headers=surface.bearer())  # type: ignore[attr-defined]
    turn = detail.json()["turns"][0]
    thread_correlation = detail.json()["thread"]["correlation_id"]

    recorded = [
        e
        for e in surface.audit.list_by_correlation_id(thread_correlation)  # type: ignore[attr-defined]
        if e.event_type == AuditEventType.TURN_RECORDED
    ]
    assert recorded[0].payload["subject_user_id"] == "alice"
    assert turn["run_id"]

    run_events = surface.audit.list_by_correlation_id(turn["run_id"])  # type: ignore[attr-defined]
    assert run_events, "the run wrote nothing to the trail"
    for event in run_events:
        # Nothing in the run's own history names the portal, because the portal was never
        # in it — the API started this run for alice, exactly as it would have on its own.
        assert "portal" not in str(event.payload).lower()


def test_the_trail_cannot_tell_which_transport_started_the_run() -> None:
    """The strong form of SC-007, by comparison rather than by inspection.

    Two runs — one through the portal, one straight through the API as the same person —
    produce the same sequence of event types with the same subject. If the portal added an
    identity, a header, or a wrapper operation, the shapes would differ here.
    """
    portal, api, surface = _portal_and_api()

    created = portal.post("/threads", follow_redirects=False)
    portal.post(
        created.headers["location"] + "/turns",
        data={"message": "via the portal", "agent_definition_id": "planner"},
        follow_redirects=False,
    )
    detail = api.get(created.headers["location"], headers=surface.bearer())  # type: ignore[attr-defined]
    via_portal = detail.json()["turns"][0]["run_id"]

    started = api.post(
        "/runs",
        json={"agent_definition_id": "planner", "requested_tools": ["echo"]},
        headers=surface.bearer(),  # type: ignore[attr-defined]
    )
    via_api = started.json()["correlation_id"]

    assert _event_shapes(surface, via_portal) == _event_shapes(surface, via_api), (
        "the trail distinguishes a portal-started run from an API-started one; "
        "the portal has acquired an identity or a code path of its own"
    )


def test_the_portal_holds_no_credential_of_its_own() -> None:
    """Structural: the relay is handed a token per request and stores nothing."""
    from surfaces.portal.relay import ApiRelay as Relay

    relay = Relay(base_url="http://api.test")
    fields = {f for f in vars(relay)}

    assert not any(
        name in fields for name in ("token", "client_secret", "credentials", "identity")
    ), f"the relay holds something credential-shaped: {fields}"
