# SPDX-License-Identifier: Apache-2.0
"""The fake IdP's authorization-code + PKCE flow, judged by what it refuses.

The portal is a **public** OIDC client: no client secret exists, so the only thing
standing between an intercepted authorization code and a token is the verifier that never
left the client. Every row below is one way that could fail, and each is a real attack
rather than a hypothetical — which is why the double runs the flow instead of returning a
pre-baked token. A double that just handed back a token would leave the portal's central
authentication guarantee completely unproven while every test passed.
"""

from __future__ import annotations

import secrets

import jwt
import pytest
from tests.harness.fake_oidc_provider import (
    AuthorizationRefused,
    FakeOIDCProvider,
    code_challenge_for,
    fake_oidc_provider,
)


def _verifier() -> str:
    return secrets.token_urlsafe(48)


def test_a_code_plus_its_verifier_becomes_a_signed_token() -> None:
    idp = fake_oidc_provider()
    verifier = _verifier()

    code = idp.authorize(code_challenge=code_challenge_for(verifier), subject="alice")
    token = idp.exchange(code=code, code_verifier=verifier)

    claims = jwt.decode(
        token,
        idp.jwks_public_key(),
        algorithms=["RS256"],
        audience=idp.audience,
        issuer=idp.issuer,
    )
    assert claims["sub"] == "alice"
    assert claims["tenant"] == "tenant-test"


def test_the_wrong_verifier_is_refused() -> None:
    """The interception PKCE exists for: the attacker has the code, not the verifier."""
    idp = fake_oidc_provider()
    code = idp.authorize(code_challenge=code_challenge_for(_verifier()))

    with pytest.raises(AuthorizationRefused) as refused:
        idp.exchange(code=code, code_verifier=_verifier())
    assert refused.value.reason == "verifier_mismatch"


def test_a_replayed_code_is_refused_even_with_the_right_verifier() -> None:
    idp = fake_oidc_provider()
    verifier = _verifier()
    code = idp.authorize(code_challenge=code_challenge_for(verifier))

    idp.exchange(code=code, code_verifier=verifier)

    with pytest.raises(AuthorizationRefused) as refused:
        idp.exchange(code=code, code_verifier=verifier)
    assert refused.value.reason == "code_already_used"


def test_a_code_is_burned_by_a_failed_exchange() -> None:
    """The ordering that makes brute-forcing a verifier pointless.

    If a failed exchange left the code alive, an attacker holding a stolen code could keep
    guessing verifiers against it. Burning before validation costs nothing — the honest
    client never needs a second attempt — and closes the loop entirely.
    """
    idp = fake_oidc_provider()
    verifier = _verifier()
    code = idp.authorize(code_challenge=code_challenge_for(verifier))

    with pytest.raises(AuthorizationRefused):
        idp.exchange(code=code, code_verifier=_verifier())

    with pytest.raises(AuthorizationRefused) as refused:
        idp.exchange(code=code, code_verifier=verifier)
    assert refused.value.reason == "code_already_used"


def test_an_expired_code_is_refused() -> None:
    idp = fake_oidc_provider()
    verifier = _verifier()
    code = idp.authorize(code_challenge=code_challenge_for(verifier))

    idp.expire_code(code)

    with pytest.raises(AuthorizationRefused) as refused:
        idp.exchange(code=code, code_verifier=verifier)
    assert refused.value.reason == "expired_code"


def test_an_unknown_code_is_refused() -> None:
    idp = fake_oidc_provider()
    with pytest.raises(AuthorizationRefused) as refused:
        idp.exchange(code="never-issued", code_verifier=_verifier())
    assert refused.value.reason == "unknown_code"


def test_plain_challenges_are_refused() -> None:
    """`plain` is permitted by RFC 7636 and by nothing here.

    Its entire effect is to send the verifier in the clear beside the code it is supposed
    to bind — the attack PKCE was written to stop, reintroduced by a parameter.
    """
    idp = fake_oidc_provider()
    with pytest.raises(AuthorizationRefused) as refused:
        idp.authorize(code_challenge="anything", code_challenge_method="plain")
    assert refused.value.reason == "unsupported_code_challenge_method"


def test_a_mismatched_redirect_uri_is_refused() -> None:
    idp = fake_oidc_provider()
    verifier = _verifier()
    code = idp.authorize(
        code_challenge=code_challenge_for(verifier), redirect_uri="http://localhost/callback"
    )

    with pytest.raises(AuthorizationRefused) as refused:
        idp.exchange(
            code=code, code_verifier=verifier, redirect_uri="http://attacker.test/callback"
        )
    assert refused.value.reason == "redirect_uri_mismatch"


def test_the_challenge_helper_matches_rfc_7636() -> None:
    """The published test vector, so the helper is right rather than merely consistent.

    RFC 7636 Appendix B: this verifier produces this challenge. Without the vector, a
    helper and its caller can agree with each other and both be wrong — which is exactly
    how a double ends up proving nothing.
    """
    assert (
        code_challenge_for("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


def test_two_providers_do_not_share_codes() -> None:
    """Separate instances model separate systems, as the token half already does."""
    one, two = FakeOIDCProvider(), FakeOIDCProvider()
    verifier = _verifier()
    code = one.authorize(code_challenge=code_challenge_for(verifier))

    with pytest.raises(AuthorizationRefused) as refused:
        two.exchange(code=code, code_verifier=verifier)
    assert refused.value.reason == "unknown_code"
