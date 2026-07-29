# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — what the browser holds, and what it cannot.

The portal's whole security posture reduces to one claim: **the browser holds an opaque
identifier and nothing else.** No token, no subject, no expiry it could reason about.
Everything below is one way that could stop being true, and the rows are what make it
checkable rather than intended.

The login flow rows matter for a second reason. The portal is a public OIDC client — no
secret exists — so PKCE and `state` are the entire defence, and a flow that accepted a
callback it did not initiate would hand a session to whoever crafted the link.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME, MAX_SESSION_SECONDS, SessionStore
from tests.harness.fake_oidc_provider import FakeOIDCProvider


@dataclass
class PortalUnderTest:
    """The client and the collaborators it was assembled with.

    Rows need the session store and the OIDC client to construct a real login — the flow is
    the thing being tested, so a fixture handing back a pre-made session would prove
    nothing about it.
    """

    client: TestClient
    oidc: OidcClient
    sessions: SessionStore


def _portal(idp: FakeOIDCProvider, *, sessions: SessionStore | None = None) -> PortalUnderTest:
    """A portal wired to the fake IdP and a relay that answers nothing.

    The relay returns empty successes: these rows are about the session, and a relay that
    reached anywhere would make them about something else.
    """

    def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
        return ApiResponse(status=200, payload={"threads": []})

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
    app = create_portal(
        relay=ApiRelay(base_url="http://api.test", transport=transport),
        oidc=oidc,
        sessions=sessions,
        secure_cookies=False,  # the test client speaks plain HTTP
    )
    return PortalUnderTest(
        client=TestClient(app, base_url="http://testserver"),
        oidc=oidc,
        sessions=app.state.sessions,
    )


def _sign_in(portal: PortalUnderTest, idp: FakeOIDCProvider) -> str:
    """Walk the real flow and return the session cookie's value."""
    state, _url = portal.oidc.begin(next_path="/")
    pending = portal.oidc._pending[state]
    code = idp.authorize(code_challenge=code_challenge_for(pending.verifier), subject="alice")
    response = portal.client.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    assert response.status_code == 303
    return str(response.cookies.get(COOKIE_NAME))


def test_the_cookie_carries_an_opaque_id_and_never_the_token() -> None:
    idp = FakeOIDCProvider()
    portal = _portal(idp)

    cookie = _sign_in(portal, idp)

    sessions = portal.sessions
    session = sessions.get(cookie)
    assert session is not None
    # The cookie is the id, and the id is not the token.
    assert cookie == session.session_id
    assert session.access_token not in cookie
    assert "." not in cookie, "the cookie looks like a JWT, which means it may be one"
    assert len(cookie) >= 32


def test_the_token_never_reaches_the_browser() -> None:
    """Not in the cookie, not in the body, not in a header."""
    idp = FakeOIDCProvider()
    portal = _portal(idp)
    cookie = _sign_in(portal, idp)
    sessions = portal.sessions
    session = sessions.get(cookie)
    assert session is not None

    page = portal.client.get("/", cookies={COOKIE_NAME: cookie})

    assert session.access_token not in page.text
    assert not any(session.access_token in v for v in page.headers.values())


def test_the_cookie_is_httponly_and_samesite_lax() -> None:
    """HttpOnly is the attribute the whole design rests on: no script may read it."""
    idp = FakeOIDCProvider()
    portal = _portal(idp)
    oidc = portal.oidc
    state, _url = oidc.begin()
    code = idp.authorize(code_challenge=code_challenge_for(oidc._pending[state].verifier))

    response = portal.client.get(f"/callback?code={code}&state={state}", follow_redirects=False)

    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "path=/" in header


def test_a_callback_with_an_unknown_state_is_refused() -> None:
    """The CSRF defence: a login nobody here started grants nothing."""
    idp = FakeOIDCProvider()
    portal = _portal(idp)
    code = idp.authorize(code_challenge=code_challenge_for("attacker-verifier"))

    response = portal.client.get(f"/callback?code={code}&state=forged", follow_redirects=False)

    assert response.status_code == 400
    assert COOKIE_NAME not in response.cookies
    assert "unknown_state" in response.text


def test_a_replayed_callback_is_refused() -> None:
    """State is consumed before the exchange, so a callback cannot be replayed."""
    idp = FakeOIDCProvider()
    portal = _portal(idp)
    oidc = portal.oidc
    state, _url = oidc.begin()
    code = idp.authorize(code_challenge=code_challenge_for(oidc._pending[state].verifier))

    first = portal.client.get(f"/callback?code={code}&state={state}", follow_redirects=False)
    second = portal.client.get(f"/callback?code={code}&state={state}", follow_redirects=False)

    assert first.status_code == 303
    assert second.status_code == 400


def test_a_failed_exchange_leaves_no_session() -> None:
    idp = FakeOIDCProvider()
    portal = _portal(idp)
    oidc = portal.oidc
    state, _url = oidc.begin()
    # A code bound to a different verifier: the interception PKCE exists for.
    code = idp.authorize(code_challenge=code_challenge_for("someone-elses-verifier"))

    response = portal.client.get(f"/callback?code={code}&state={state}", follow_redirects=False)

    sessions = portal.sessions
    assert response.status_code == 400
    assert sessions.sessions == {}


def test_an_expired_session_sends_the_person_back_to_sign_in() -> None:
    """Not an error page — a re-login. The person did nothing wrong."""
    sessions = SessionStore()
    idp = FakeOIDCProvider()
    portal = _portal(idp, sessions=sessions)
    session = sessions.create(
        subject_user_id="alice",
        tenant_id="tenant-test",
        access_token="tok",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    page = portal.client.get("/", cookies={COOKIE_NAME: session.session_id})

    assert "Sign in" in page.text
    assert sessions.get(session.session_id) is None


def test_a_session_dies_at_the_hard_bound_even_with_a_long_lived_token() -> None:
    sessions = SessionStore()
    session = sessions.create(
        subject_user_id="alice",
        tenant_id="tenant-test",
        access_token="tok",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    aged = type(session)(
        session_id=session.session_id,
        subject_user_id=session.subject_user_id,
        tenant_id=session.tenant_id,
        access_token=session.access_token,
        expires_at=session.expires_at,
        created_at=datetime.now(UTC) - timedelta(seconds=MAX_SESSION_SECONDS + 1),
    )
    sessions.sessions[session.session_id] = aged

    assert sessions.get(session.session_id) is None


def test_signing_out_destroys_the_session_server_side() -> None:
    """Clearing the cookie is not enough — the token must stop being usable."""
    idp = FakeOIDCProvider()
    portal = _portal(idp)
    cookie = _sign_in(portal, idp)
    sessions = portal.sessions

    portal.client.post("/logout", cookies={COOKIE_NAME: cookie}, follow_redirects=False)

    assert sessions.get(cookie) is None


def test_a_session_repr_does_not_print_its_token() -> None:
    """A traceback or a debugger must not be how a token reaches a log."""
    sessions = SessionStore()
    session = sessions.create(
        subject_user_id="alice",
        tenant_id="tenant-test",
        access_token="super-secret-token",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    assert "super-secret-token" not in repr(session)


def test_pending_logins_do_not_accumulate() -> None:
    """An unauthenticated allocation keyed by an attacker-supplied round trip expires."""
    from surfaces.portal.oidc import PENDING_LIFETIME, PendingLogin

    oidc = OidcClient(
        issuer="https://idp.test/",
        client_id="portal",
        redirect_uri="http://testserver/callback",
        authorize_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
    )
    state, _ = oidc.begin()
    oidc._pending[state] = PendingLogin(
        state=state,
        verifier="v",
        created_at=datetime.now(UTC) - PENDING_LIFETIME - timedelta(seconds=1),
    )

    oidc.begin()  # any new login sweeps

    assert state not in oidc._pending


def test_an_absolute_next_path_is_refused() -> None:
    """A login link must not be able to make the portal an open redirector."""
    oidc = OidcClient(
        issuer="https://idp.test/",
        client_id="portal",
        redirect_uri="http://testserver/callback",
        authorize_endpoint="http://idp.test/authorize",
        token_endpoint="http://idp.test/token",
    )

    state, _ = oidc.begin(next_path="https://evil.test/steal")
    assert oidc._pending[state].next_path == "/"

    state, _ = oidc.begin(next_path="//evil.test/steal")
    assert oidc._pending[state].next_path == "/"
