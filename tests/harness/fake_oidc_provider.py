# SPDX-License-Identifier: Apache-2.0
"""A fake OIDC provider that signs real JWTs with a real key.

**The only fake in this feature**, and correctly so: the customer's identity provider is
outside our boundary and we do not deploy it. Everything else — Vault, Postgres,
allocations — runs for real.

The rule that makes this double worth having: it must run real flows and produce real
signatures. A double that returned a pre-baked subject without signing anything would
leave this feature's central guarantee — that identity is *verified* before it becomes the
subject of everything downstream — completely unproven, while every test passed. So this
generates an RSA key, serves a genuine JWKS document, and signs tokens that PyJWT verifies
against it.

It can also produce the tokens that must be **refused**, which is most of what it is for:
expired, not-yet-valid, wrong issuer, wrong audience, signed by the wrong key, and
``alg: none``. A verifier is judged by what it rejects.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://idp.test.invalid/"
AUDIENCE = "harness-api"


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@dataclass
class FakeOIDCProvider:
    """Generates a signing key and issues genuinely signed tokens."""

    issuer: str = ISSUER
    audience: str = AUDIENCE
    key_id: str = "test-key-1"
    _key: rsa.RSAPrivateKey = field(init=False)
    _other_key: rsa.RSAPrivateKey = field(init=False)

    def __post_init__(self) -> None:
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        # A second, valid-but-wrong key. Signing with this is how a token that is
        # perfectly well-formed still has to be refused.
        self._other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # ------------------------------------------------------------------ JWKS

    def jwks(self) -> dict[str, Any]:
        """The document a verifier fetches. Public material only."""
        numbers = self._key.public_key().public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self.key_id,
                    "n": _b64url_uint(numbers.n),
                    "e": _b64url_uint(numbers.e),
                }
            ]
        }

    def jwks_json(self) -> str:
        return json.dumps(self.jwks())

    def jwks_public_key(self) -> Any:
        """The public key a verifier would extract from the JWKS document."""
        return self._key.public_key()

    # ------------------------------------------------------------------ tokens

    def token(
        self,
        *,
        subject: str = "user-1",
        tenant: str | None = "tenant-test",
        claims: dict[str, Any] | None = None,
        lifetime: timedelta = timedelta(minutes=5),
        issued_at: datetime | None = None,
        issuer: str | None = None,
        audience: str | None = None,
        sign_with_wrong_key: bool = False,
    ) -> str:
        now = issued_at or datetime.now(UTC)
        payload: dict[str, Any] = {
            "iss": issuer if issuer is not None else self.issuer,
            "aud": audience if audience is not None else self.audience,
            "sub": subject,
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + lifetime).timestamp()),
        }
        if tenant is not None:
            payload["tenant"] = tenant
        payload.update(claims or {})
        key = self._other_key if sign_with_wrong_key else self._key
        return jwt.encode(payload, key, algorithm="RS256", headers={"kid": self.key_id})

    # ---- the tokens that must be refused ----

    def expired_token(self, **kwargs: Any) -> str:
        return self.token(
            issued_at=datetime.now(UTC) - timedelta(hours=2),
            lifetime=timedelta(minutes=5),
            **kwargs,
        )

    def not_yet_valid_token(self, **kwargs: Any) -> str:
        return self.token(issued_at=datetime.now(UTC) + timedelta(hours=1), **kwargs)

    def wrong_issuer_token(self, **kwargs: Any) -> str:
        return self.token(issuer="https://attacker.test.invalid/", **kwargs)

    def wrong_audience_token(self, **kwargs: Any) -> str:
        return self.token(audience="some-other-service", **kwargs)

    def wrong_key_token(self, **kwargs: Any) -> str:
        return self.token(sign_with_wrong_key=True, **kwargs)

    def unsigned_token(self, subject: str = "user-1") -> str:
        """``alg: none``.

        The classic algorithm-confusion attack, and the reason this feature adopted PyJWT
        instead of hand-rolling verification. A verifier that reads the algorithm from the
        token's own header accepts this, fails open, and passes every test anyone thinks
        to write — because it *does* verify correctly-signed tokens.
        """
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        now = datetime.now(UTC)
        body = base64.urlsafe_b64encode(
            json.dumps(
                {
                    "iss": self.issuer,
                    "aud": self.audience,
                    "sub": subject,
                    "tenant": "tenant-test",
                    "exp": int((now + timedelta(minutes=5)).timestamp()),
                }
            ).encode()
        )
        return f"{header.rstrip(b'=').decode()}.{body.rstrip(b'=').decode()}."


def fake_oidc_provider() -> FakeOIDCProvider:
    return FakeOIDCProvider()


__all__ = ["AUDIENCE", "ISSUER", "FakeOIDCProvider", "fake_oidc_provider"]
