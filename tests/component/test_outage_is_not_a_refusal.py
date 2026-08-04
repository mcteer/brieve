# SPDX-License-Identifier: Apache-2.0
"""Not knowing who somebody is, is not the same as knowing they may not.

The maintainer was told *"The platform refused this request and gave no reason."* Both halves
were false. Nothing had refused him — his access was intact — and there was a reason, sitting in
the API's log, where verification had failed reading the trust store on an expired workload
identity. It reached him as an unhandled 500 with no body, and the portal read a failure with no
reason as a refusal.

Two rows for the two mistakes, and they are different mistakes:

  * The API turned an availability failure into an unclassified crash. A trust store it cannot
    read is a 503 — come back — not a 401 or 403, which mean take it up with somebody.
  * The portal called a 5xx a refusal. A refusal is a decision ABOUT A PERSON and always the
    API's to state; a 5xx is the platform failing to function, which is not about them at all.

Neither fix grants anything. The request is still denied, nothing executes, and no record is
reached — what changed is that the answer now says which kind of nothing it is.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from core.identity.mappings_store import ClaimMappingsUnavailable
from surfaces.portal.app import create_portal
from surfaces.portal.oidc import OidcClient, code_challenge_for
from surfaces.portal.relay import ApiRelay, ApiResponse
from surfaces.portal.session import COOKIE_NAME
from tests.harness.api_fixtures import surface_under_test


class _TrustStoreDown:
    """A verifier that cannot reach the mappings — the shape of an expired identity."""

    def verify(self, token: str | None) -> Any:
        raise ClaimMappingsUnavailable(
            "claim mappings could not be listed at 'harness-authority/metadata/claim-mappings'"
        )


def test_an_unreadable_trust_store_is_unavailable_not_forbidden() -> None:
    """503, and a reason code the surface already speaks.

    A 500 says nothing and reaches the caller as a body-less failure; a 401 or 403 would be a
    claim about this person's access that the platform is in no position to make — it could not
    even read the mappings.
    """
    surface = surface_under_test()
    surface.app.state.token_verifier = _TrustStoreDown()

    response = TestClient(surface.app).post(
        "/ask", json={"question": "how do I run a Vault cluster?"}, headers=surface.bearer()
    )

    assert response.status_code == 503, (
        "an unreadable trust store came back as something other than 'come back later'"
    )
    assert response.json()["detail"] == "identity_mappings_unavailable"


def test_nothing_executes_when_identity_cannot_be_established() -> None:
    """The half that must not change. Classifying the failure must not soften it."""
    surface = surface_under_test()
    surface.app.state.token_verifier = _TrustStoreDown()
    before = len(surface.audit.all_entries())

    TestClient(surface.app).post(
        "/ask", json={"question": "how do I run a Vault cluster?"}, headers=surface.bearer()
    )

    assert len(surface.audit.all_entries()) == before, (
        "a request whose subject could not be established still reached the record"
    )


@pytest.fixture
def portal_over() -> Any:
    """A signed-in portal whose relay returns whatever status a row asks for."""

    def _build(status: int, payload: Any) -> TestClient:
        surface = surface_under_test()

        def transport(*, method: str, url: str, token: str, json_body: object) -> ApiResponse:
            if url.endswith("/ask"):
                return ApiResponse(status=status, payload=payload)
            return ApiResponse(status=200, payload={"threads": []})

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
                relay=ApiRelay(base_url="http://api.test", transport=transport), oidc=oidc
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

    return _build


@pytest.mark.parametrize("status", [500, 502, 503])
def test_the_portal_never_calls_a_broken_platform_a_refusal(portal_over: Any, status: int) -> None:
    """The sentence the maintainer actually read, made unreachable for a 5xx."""
    client = portal_over(status, None)

    body = client.post("/ask", data={"question": "how do I run a Vault cluster?"}).text

    assert "refused this request and gave no reason" not in body
    assert "The platform could not be asked" in body
    assert "Nothing about your access has changed" in body


@pytest.mark.parametrize("status", [403, 503])
def test_a_platform_that_spoke_is_always_quoted(portal_over: Any, status: int) -> None:
    """The row that caught the first attempt at this fix.

    Branching on `status >= 500` swallowed *"no model credential source is configured for this
    surface"* — a 503 carrying one of the precise sentences this page exists to relay. Whether
    the platform SAID something is the question; the status code is not.
    """
    sentence = "no model credential source is configured for this surface"
    client = portal_over(status, {"detail": sentence})

    body = client.post("/ask", data={"question": "how do I run a Vault cluster?"}).text

    assert sentence in body, f"a {status} carrying a real reason had it swallowed"
    assert "could not be asked" not in body


def test_a_refusal_still_carries_the_platforms_own_words(portal_over: Any) -> None:
    """The thin-client rule is untouched below 500 (ADR-0034).

    A 4xx IS a decision about this person, the API is the only thing entitled to state it, and
    the portal must keep rendering that sentence rather than inventing a friendlier one.
    """
    client = portal_over(403, {"detail": "unmapped_claim"})

    body = client.post("/ask", data={"question": "how do I run a Vault cluster?"}).text

    assert "unmapped_claim" in body
    assert "The platform did not answer this" in body
    assert "could not be asked" not in body
