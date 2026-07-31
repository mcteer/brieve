# SPDX-License-Identifier: Apache-2.0
"""The portal's OIDC client: authorization code + PKCE, and no secret anywhere.

**A public client, deliberately.** A confidential client would need a secret in the
portal's configuration, which is the static credential Principle IV prohibits without
exception. PKCE exists precisely so a client with no secret can still prove that the party
redeeming an authorization code is the party that requested it — the verifier never leaves
this process, so an intercepted code redeems nothing.

**S256 only.** RFC 7636 permits `plain`, whose entire effect is to send the verifier in the
clear beside the code it exists to bind. Supporting it would be reintroducing the attack
PKCE was written to stop, by way of a parameter.

This module builds requests and validates the callback. It holds no session and stores no
token — that is `session.py`, and the separation is what keeps "what the browser gets" a
question with one place to look.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

#: How long an unfinished login may sit before its state is discarded.
#:
#: A pending authorization is an unauthenticated allocation of memory keyed by an attacker-
#: supplied round trip, so it expires whether or not anyone comes back.
PENDING_LIFETIME = timedelta(minutes=10)


class LoginRefused(Exception):
    """The login could not be completed. Carries a reason code, never a token."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def code_challenge_for(verifier: str) -> str:
    """S256: BASE64URL(SHA256(verifier)), unpadded — RFC 7636 §4.2."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class PendingLogin:
    """One in-flight authorization: what we sent, so the callback can be checked."""

    state: str
    verifier: str
    created_at: datetime
    #: Where to send the person after a successful login. Portal-relative only — an
    #: absolute URL here would make the portal an open redirector for anyone who can craft
    #: a login link.
    next_path: str = "/"


@dataclass
class OidcClient:
    """Builds the authorization request and redeems the code for a token."""

    issuer: str
    client_id: str
    redirect_uri: str
    authorize_endpoint: str
    token_endpoint: str
    #: Which API the returned access token is FOR.
    #:
    #: Optional because OIDC does not require it and the development provider does not
    #: want it. Necessary against a real one: Auth0 issues an **opaque** token when no
    #: audience is requested — not a JWT at all — and the API then refuses it as
    #: `unverifiable_identity`, which names the token rather than the missing parameter.
    #: Okta and Ping behave the same way for the same reason: without an audience there is
    #: no resource server whose keys and claims the token should be shaped for.
    audience: str | None = None
    #: Injected in tests so the flow runs against the fake provider without HTTP.
    exchange: Any | None = None
    _pending: dict[str, PendingLogin] = field(default_factory=dict)

    def begin(self, *, next_path: str = "/") -> tuple[str, str]:
        """Return ``(state, authorization_url)`` and remember what we sent.

        ``state`` binds the callback to this request; the verifier binds the code to this
        client. Both are needed: state alone stops a cross-site login CSRF, and the
        verifier alone stops a stolen code being redeemed.
        """
        self._expire()
        state = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        self._pending[state] = PendingLogin(
            state=state,
            verifier=verifier,
            created_at=datetime.now(UTC),
            next_path=_safe_next(next_path),
        )
        query = urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "openid profile",
                "state": state,
                "code_challenge": code_challenge_for(verifier),
                "code_challenge_method": "S256",
                # Omitted entirely rather than sent empty: a provider that does not use
                # this parameter must not receive it, and `audience=` reads as a request
                # for an audience named "" rather than as no request at all.
                **({"audience": self.audience} if self.audience else {}),
            }
        )
        return state, f"{self.authorize_endpoint}?{query}"

    def complete(self, *, code: str, state: str) -> tuple[str, str]:
        """Redeem the code. Returns ``(access_token, next_path)`` or refuses.

        The pending record is consumed **before** the exchange is attempted, so a failed
        callback cannot be retried against the same state — the same reason the IdP burns
        an authorization code before validating its verifier.
        """
        pending = self._pending.pop(state, None)
        if pending is None:
            raise LoginRefused("unknown_state")
        if datetime.now(UTC) - pending.created_at > PENDING_LIFETIME:
            raise LoginRefused("expired_state")

        try:
            token = self._redeem(code=code, verifier=pending.verifier)
        except LoginRefused:
            raise
        except Exception as exc:  # noqa: BLE001 — the reason is the IdP's, not ours to guess
            raise LoginRefused("exchange_failed") from exc
        if not token:
            raise LoginRefused("no_token_returned")
        return token, pending.next_path

    def _redeem(self, *, code: str, verifier: str) -> str:
        if self.exchange is not None:
            token: str = self.exchange(code=code, code_verifier=verifier)
            return token
        body = urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "code_verifier": verifier,
            }
        ).encode()
        request = urllib.request.Request(  # noqa: S310 — operator-supplied issuer, fixed scheme
            self.token_endpoint,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            parsed = json.loads(response.read())
        return str(parsed.get("access_token") or "")

    def _expire(self) -> None:
        cutoff = datetime.now(UTC) - PENDING_LIFETIME
        for state in [s for s, p in self._pending.items() if p.created_at < cutoff]:
            del self._pending[state]

    @property
    def pending_count(self) -> int:
        """For rows that assert nothing accumulates. Never used by the flow."""
        return len(self._pending)


def _safe_next(path: str) -> str:
    """Only portal-relative paths survive.

    An absolute URL — or a protocol-relative `//evil.test` — would make the portal an open
    redirector, and a login link is exactly the thing people click without reading.
    """
    if not path.startswith("/") or path.startswith("//"):
        return "/"
    return path


__all__ = [
    "PENDING_LIFETIME",
    "LoginRefused",
    "OidcClient",
    "PendingLogin",
    "code_challenge_for",
]
