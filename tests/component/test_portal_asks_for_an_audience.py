# SPDX-License-Identifier: Apache-2.0
"""What the portal asks the identity provider for, and what it must not ask for.

The authorization request is the one place the portal states which API the resulting
token is for. Against the development provider that is unnecessary, and the portal shipped
without it. Against a real one it decides what KIND of token comes back: Auth0 issues an
**opaque** token when no audience is requested — not a JWT, nothing our verifier can even
parse — and the API then refuses it as `unverifiable_identity`. That error names the token,
so whoever debugs it inspects the token, the JWKS and the signing algorithm before
suspecting a query parameter that is not there. Okta and Ping behave the same way, for the
same reason: without an audience there is no resource server for the token to be shaped
against.
"""

from __future__ import annotations

import urllib.parse

from surfaces.portal.oidc import OidcClient


def client(**kwargs: object) -> OidcClient:
    return OidcClient(
        issuer="https://idp.test/",
        client_id="portal",
        redirect_uri="http://localhost:8082/callback",
        authorize_endpoint="https://idp.test/authorize",
        token_endpoint="https://idp.test/oauth/token",
        **kwargs,  # type: ignore[arg-type]
    )


def query_of(url: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlparse(url).query)


def test_the_audience_is_forwarded_when_configured() -> None:
    _, url = client(audience="https://api.brieve.dev").begin()

    assert query_of(url)["audience"] == ["https://api.brieve.dev"]


def test_no_audience_parameter_is_sent_when_none_is_configured() -> None:
    """Absent, not empty.

    A provider that does not use this parameter must not receive it: `audience=` reads as
    a request for an audience named "" rather than as no request at all, and a strict
    provider is entitled to reject it.
    """
    assert "audience" not in query_of(client().begin()[1])
    assert "audience" not in query_of(client(audience="").begin()[1])


def test_asking_for_an_audience_does_not_disturb_pkce() -> None:
    """The parameters that make this flow safe are unchanged by the new one.

    Worth asserting together rather than trusting: an audience is added to the same dict
    that carries the challenge, and a mistake there would produce a login that still works
    while proving nothing about who is redeeming the code.
    """
    query = query_of(client(audience="https://api.brieve.dev").begin()[1])

    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] and query["code_challenge"][0]
    assert query["response_type"] == ["code"]
    assert "client_secret" not in query, "the portal is a public client and has no secret"
