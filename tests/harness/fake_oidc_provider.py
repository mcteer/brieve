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

**012 grew it an authorization-code + PKCE flow** (`authorize` / `exchange`), because the
portal is a public OIDC client and a browser has to actually walk the flow. The same rule
applies as to the tokens: the flow is judged by what it refuses — a wrong verifier, a
replayed code, an expired code, and `plain` challenges are all reproducible here, and the
portal's own rows assert each is rejected. **S256 only**: `plain` is accepted by the
specification and by nothing here, because a `plain` challenge is the verifier travelling
in the clear beside the code it is supposed to protect.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER = "https://idp.test.invalid/"
AUDIENCE = "harness-api"

#: How long an authorization code stays exchangeable. Short by design: a code is a
#: single-use bearer of the right to obtain a token, and every second it lives is a second
#: it can be stolen from a browser history, a proxy log, or a referrer header.
CODE_LIFETIME = timedelta(minutes=1)


class AuthorizationRefused(Exception):
    """The flow refused. Carries a code, not a message, so rows assert on the reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def code_challenge_for(verifier: str) -> str:
    """S256: BASE64URL(SHA256(verifier)), unpadded — RFC 7636 §4.2.

    Here rather than only in the client so a row can construct a challenge without
    importing the thing it is testing, which would make the test agree with the
    implementation by construction rather than by correctness.
    """
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass
class _PendingCode:
    """An issued authorization code, and everything needed to refuse its misuse."""

    subject: str
    tenant: str | None
    claims: dict[str, Any]
    code_challenge: str
    redirect_uri: str
    issued_at: datetime
    used: bool = False


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@dataclass
class FakeOIDCProvider:
    """Generates a signing key and issues genuinely signed tokens.

    Instantiate more than one to model separate providers — the human IdP and the workload
    identity issuer are different systems with different keys, and a double that shared a
    key between them would hide a verifier that ignored the issuer.
    """

    issuer: str = ISSUER
    audience: str = AUDIENCE
    key_id: str = "test-key-1"
    _key: rsa.RSAPrivateKey = field(init=False)
    _other_key: rsa.RSAPrivateKey = field(init=False)
    _codes: dict[str, _PendingCode] = field(init=False, default_factory=dict)

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

    # ------------------------------------------------------ authorization code + PKCE

    def authorize(
        self,
        *,
        code_challenge: str,
        code_challenge_method: str = "S256",
        redirect_uri: str = "http://localhost/callback",
        subject: str = "user-1",
        tenant: str | None = "tenant-test",
        claims: dict[str, Any] | None = None,
    ) -> str:
        """The `/authorize` half: the person has authenticated; here is a code.

        **`plain` is refused**, not merely discouraged. RFC 7636 permits it and its whole
        effect is to send the verifier in the clear alongside the code it exists to bind —
        which is the attack PKCE was written to stop, reintroduced by a parameter.
        """
        if code_challenge_method != "S256":
            raise AuthorizationRefused("unsupported_code_challenge_method")
        if not code_challenge:
            raise AuthorizationRefused("missing_code_challenge")
        code = secrets.token_urlsafe(24)
        self._codes[code] = _PendingCode(
            subject=subject,
            tenant=tenant,
            claims=dict(claims or {}),
            code_challenge=code_challenge,
            redirect_uri=redirect_uri,
            issued_at=datetime.now(UTC),
        )
        return code

    def exchange(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str = "http://localhost/callback",
        lifetime: timedelta = timedelta(minutes=5),
    ) -> str:
        """The `/token` half: a code plus its verifier becomes a signed access token.

        Four refusals, each of which is a real attack rather than a hypothetical:

        - **unknown code** — a guessed or fabricated code;
        - **used code** — replay, which is why the code is marked before the verifier is
          even checked: a replayed code is dead whether or not the attacker also has the
          verifier;
        - **expired code** — a code recovered later from a log or history;
        - **verifier mismatch** — the interception PKCE exists for, where an attacker has
          the code from a redirect but not the verifier that never left the client.
        """
        pending = self._codes.get(code)
        if pending is None:
            raise AuthorizationRefused("unknown_code")
        if pending.used:
            raise AuthorizationRefused("code_already_used")
        # Burned before validation, deliberately. A code that survives a failed exchange
        # is a code an attacker may keep guessing verifiers against.
        pending.used = True
        if datetime.now(UTC) - pending.issued_at > CODE_LIFETIME:
            raise AuthorizationRefused("expired_code")
        if redirect_uri != pending.redirect_uri:
            raise AuthorizationRefused("redirect_uri_mismatch")
        if not secrets.compare_digest(code_challenge_for(code_verifier), pending.code_challenge):
            raise AuthorizationRefused("verifier_mismatch")
        return self.token(
            subject=pending.subject,
            tenant=pending.tenant,
            claims=pending.claims,
            lifetime=lifetime,
        )

    def expire_code(self, code: str) -> None:
        """Age a code past its lifetime, so a row need not sleep for a minute."""
        pending = self._codes.get(code)
        if pending is not None:
            pending.issued_at = pending.issued_at - CODE_LIFETIME - timedelta(seconds=1)


def fake_oidc_provider() -> FakeOIDCProvider:
    return FakeOIDCProvider()


__all__ = [
    "AUDIENCE",
    "CODE_LIFETIME",
    "ISSUER",
    "AuthorizationRefused",
    "FakeOIDCProvider",
    "code_challenge_for",
    "fake_oidc_provider",
]
