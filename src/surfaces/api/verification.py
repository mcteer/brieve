# SPDX-License-Identifier: Apache-2.0
"""Turning a token into an :class:`AuthenticatedSubject`.

This module is the transport's half of identity: core defines what a subject *is*, and
this decides whether a presented token establishes one. It lives here rather than in core
because it is the part that needs a JWT library, and the core install must not acquire one.

Three things are deliberate and each fails open if got wrong:

**The algorithm is pinned by us, never read from the token.** ``alg: none`` and
algorithm-confusion attacks work precisely because a verifier trusts the header of the
thing it is verifying. PyJWT is used rather than hand-rolled signature checking for the
same reason — a subtly wrong verifier accepts forged tokens and passes every test anyone
thinks to write, because it does verify legitimate ones.

**Issuer and audience are checked, not just the signature.** A validly-signed token for a
different audience is a token someone else was given, replayed here.

**JWKS keys are cached with a bounded TTL; identities never are.** These are different
things and conflating them is what makes "fail closed when the IdP is unreachable" seem
contradictory. A JWKS document is public verification material the provider publishes for
anyone to fetch; a token is an identity claim with its own expiry. Caching the first is how
every OIDC resource server works. Honouring the second past its ``exp`` is what FR-016
forbids, and nothing here does it. With a cold or stale cache and an unreachable provider,
authentication fails closed — but a valid unexpired token does not stop working because
the provider blinked, which would convert one shared outage into thousands of individual
failures.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import jwt
from jwt import PyJWKClient

from core.errors import CoreError
from core.identity.claims import ClaimMapping, resolve_roles
from core.identity.types import AuthenticatedSubject, SubjectKind

#: We choose these. The token does not get a vote.
ALLOWED_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384"]

DEFAULT_JWKS_TTL_SECONDS = 600.0
DEFAULT_TENANT_CLAIM = "tenant"


class AuthenticationRefused(CoreError):
    """The caller did not establish an identity. Nothing executes."""

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class _KeyCache:
    """Bounded-TTL cache of public verification material.

    Bounded rather than unbounded because key rotation must take effect: an unbounded
    cache would keep verifying against a key the provider revoked.
    """

    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._keys: dict[str, Any] = {}
        self._fetched_at: float | None = None

    def is_fresh(self) -> bool:
        return self._fetched_at is not None and (self._clock() - self._fetched_at) < self._ttl

    def get(self, kid: str) -> Any | None:
        return self._keys.get(kid) if self.is_fresh() else None

    def put(self, keys: dict[str, Any]) -> None:
        self._keys = keys
        self._fetched_at = self._clock()


class TokenVerifier:
    """Verifies OIDC tokens and maps their claims onto a subject."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_uri: str | None = None,
        mappings: list[ClaimMapping] | None = None,
        tenant_claim: str = DEFAULT_TENANT_CLAIM,
        jwks_ttl_seconds: float = DEFAULT_JWKS_TTL_SECONDS,
        key_loader: Callable[[], dict[str, Any]] | None = None,
        subject_kind: SubjectKind = SubjectKind.HUMAN,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._mappings = mappings or []
        self._tenant_claim = tenant_claim
        self._subject_kind = subject_kind
        self._cache = _KeyCache(jwks_ttl_seconds)
        if key_loader is not None:
            self._key_loader = key_loader
        elif jwks_uri is not None:
            client = PyJWKClient(jwks_uri, cache_keys=False)
            self._key_loader = lambda: {
                k.key_id: k.key for k in client.get_jwk_set().keys if k.key_id
            }
        else:  # pragma: no cover - constructor misuse
            raise ValueError("one of jwks_uri or key_loader is required")

    def _key_for(self, kid: str | None) -> Any:
        if kid is None:
            raise AuthenticationRefused(
                "token names no key id", reason_code="unverifiable_identity"
            )
        cached = self._cache.get(kid)
        if cached is not None:
            return cached
        try:
            keys = self._key_loader()
        except Exception as exc:
            # Cold or stale cache plus an unreachable provider. Fail closed (FR-016).
            raise AuthenticationRefused(
                f"identity provider unreachable and no fresh key material: {type(exc).__name__}",
                reason_code="idp_unreachable",
            ) from exc
        self._cache.put(keys)
        key = keys.get(kid)
        if key is None:
            raise AuthenticationRefused(
                "token signed by an unknown key", reason_code="unverifiable_identity"
            )
        return key

    def verify(self, token: str | None) -> AuthenticatedSubject:
        """Return the subject this token establishes, or refuse with nothing executed."""
        if not token or not token.strip():
            raise AuthenticationRefused("no identity presented", reason_code="absent_identity")

        try:
            header = jwt.get_unverified_header(token)
        except Exception as exc:
            raise AuthenticationRefused(
                "token is malformed", reason_code="unverifiable_identity"
            ) from exc

        # Read the kid to select a key, and nothing else. In particular NOT the algorithm:
        # `algorithms=` below is ours, so `alg: none` selects no permitted algorithm and is
        # refused rather than honoured.
        key = self._key_for(header.get("kid"))

        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationRefused(
                "identity has expired", reason_code="expired_identity"
            ) from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationRefused(
                f"identity could not be verified: {type(exc).__name__}",
                reason_code="unverifiable_identity",
            ) from exc

        tenant = str(claims.get(self._tenant_claim, "") or "").strip()
        if not tenant:
            raise AuthenticationRefused("identity carries no tenant claim", reason_code="no_tenant")

        roles = resolve_roles(claims, self._mappings)
        if not roles:
            # Distinct from a failed signature on purpose. An operator debugging an
            # integration needs to tell "your token is bad" from "your claim is not
            # mapped", and both refuse identically without the distinction.
            raise AuthenticationRefused(
                "identity claims map to no role", reason_code="unmapped_claim"
            )

        return AuthenticatedSubject(
            subject_user_id=str(claims["sub"]),
            tenant_id=tenant,
            roles=roles,
            subject_kind=self._subject_kind,
            expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=UTC),
        )


class FederatedVerifier:
    """Accepts a human identity or a federated workload identity — and nothing else.

    Machines authenticate by presenting a token from their own workload identity provider,
    verified exactly as a human's is: real signature, pinned algorithm, checked issuer and
    audience. **There is no third branch**, and that is the point of the class existing.
    A static-key path would naturally be added here, beside two working mechanisms, as
    "just for automation" — so this is the place the absence has to be visible and tested.

    Order matters only for the reason code a caller sees. Each verifier is tried, and the
    refusal reported is the *most specific* one encountered: a token that verified but
    mapped to no role should say so rather than being reported as unverifiable just
    because a later issuer also rejected it.
    """

    #: Lower is more specific. A refusal that got further into verification tells the
    #: caller more, so it wins over one that failed at the first check.
    _SPECIFICITY = {
        "unmapped_claim": 0,
        "no_tenant": 1,
        "expired_identity": 2,
        "idp_unreachable": 3,
        "unverifiable_identity": 4,
        "absent_identity": 5,
    }

    def __init__(self, verifiers: list[TokenVerifier]) -> None:
        if not verifiers:  # pragma: no cover - assembly error
            raise ValueError("at least one verifier is required")
        self._verifiers = verifiers

    def verify(self, token: str | None) -> AuthenticatedSubject:
        best: AuthenticationRefused | None = None
        for verifier in self._verifiers:
            try:
                return verifier.verify(token)
            except AuthenticationRefused as exc:
                if best is None or self._rank(exc) < self._rank(best):
                    best = exc
        assert best is not None
        raise best

    def _rank(self, exc: AuthenticationRefused) -> int:
        return self._SPECIFICITY.get(exc.reason_code, 99)


__all__ = [
    "ALLOWED_ALGORITHMS",
    "AuthenticationRefused",
    "FederatedVerifier",
    "TokenVerifier",
]
