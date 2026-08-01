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
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient

from core.errors import CoreError
from core.identity.claims import ClaimMapping, resolve_roles
from core.identity.kind import looks_like_a_machine_credential
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


class IdentityVerifier(Protocol):
    """Anything that turns a token into a subject, or refuses.

    The surface needs exactly this and knows nothing else about its verifier. A protocol
    rather than the concrete class because there are two implementations, and the
    composing one — `FederatedVerifier` — is what a real assembly builds: typing the app
    against `TokenVerifier` made the composed form a type error, which is the wrong way
    round for the only shape production uses.
    """

    def verify(self, token: str | None) -> AuthenticatedSubject: ...


class TokenVerifier:
    """Verifies OIDC tokens and maps their claims onto a subject."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_uri: str | None = None,
        mappings: list[ClaimMapping] | None = None,
        mappings_source: Callable[[], list[ClaimMapping]] | None = None,
        tenant_claim: str = DEFAULT_TENANT_CLAIM,
        jwks_ttl_seconds: float = DEFAULT_JWKS_TTL_SECONDS,
        key_loader: Callable[[], dict[str, Any]] | None = None,
        subject_kind: SubjectKind = SubjectKind.HUMAN,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        # Resolved per verification rather than captured at construction, so a mapping
        # that clears quorum takes effect without restarting the surface. A restart is a
        # deploy, and needing one to complete an approval means the gate that governs
        # authority changes is only half the mechanism — the other half being whoever
        # remembers to bounce the service.
        #
        # Literal `mappings` stays for tests and for a deployment that pins its grants in
        # configuration. Both is a contradiction, not a merge: a caller that passed each
        # of them meant one of the two and would get a set matching neither.
        if mappings is not None and mappings_source is not None:
            raise ValueError("pass either mappings or mappings_source, not both")
        frozen = list(mappings or [])
        self._mappings_source: Callable[[], list[ClaimMapping]] = (
            mappings_source if mappings_source is not None else lambda: frozen
        )
        self._tenant_claim = tenant_claim
        self._subject_kind = subject_kind
        self._cache = _KeyCache(jwks_ttl_seconds)
        if key_loader is not None:
            self._key_loader = key_loader
        elif jwks_uri is not None:
            # `cache_jwk_set=False` IS THE POINT OF THIS LINE, and its absence made the
            # unknown-key path below effectively dead code.
            #
            # `cache_keys=False` was already the library default and governs a different cache
            # — an LRU over signing keys. Left at their defaults, `cache_jwk_set=True` and
            # `lifespan=300` meant the JWK SET itself was held for five minutes inside the
            # client. So `_key_for` would meet a key id it did not recognise, refetch exactly as
            # it was written to, and receive the same stale set back — finding nothing.
            #
            # MEASURED, not reasoned: after the provider rotated, a valid token was refused for
            # ~250 seconds and then accepted, with no restart. The refusal was
            # `unverifiable_identity`, which names the symptom and not the cause.
            #
            # This is not a development-lane concern. Against any real provider, a key rotation
            # was invisible here for up to five minutes while this code looked like it handled
            # rotation immediately.
            #
            # **Staleness is now bounded by `_KeyCache` alone**, which is the one that fails
            # closed and is written to. FOR REVIEW: an unknown key id now reaches the provider
            # rather than a local cache, so a caller presenting fabricated ids can prompt a
            # fetch per request. That is the cost of resolving rotation promptly, it is one GET
            # to the provider, and rate-limiting it belongs to the provider rather than here —
            # but it is a real change in outbound behaviour and is named rather than buried.
            client = PyJWKClient(jwks_uri, cache_keys=False, cache_jwk_set=False)
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

    def _require_declared_kind(self, claims: dict[str, Any]) -> None:
        """Refuse a machine's credential where a person's was expected.

        `subject_kind` used to be asserted onto every subject this verifier produced,
        unchecked. That is sound only while each kind arrives from its own issuer — and
        Auth0, Okta, Ping and Entra all serve `client_credentials` and `authorization_code`
        from ONE issuer, one JWKS, one audience. So a surface configured for people
        recorded a machine as a person, and, worse, **let it in**: a leaked client secret
        was a working operator login that the trail showed as somebody signing in.

        **Asymmetric, deliberately.** Positive evidence of a machine contradicts a `HUMAN`
        declaration, so it is refused. The reverse is not true, and enforcing it would be a
        mistake: a Nomad workload identity carries `sub = <job id>` and no `azp`, no `gty`,
        nothing marking it as a machine at all — because it comes from an issuer that
        serves nothing else. There the declaration IS the evidence, and demanding a marker
        would refuse every genuine federated workload.

        The residual risk that leaves is ordering. Where one issuer serves both kinds, a
        person's token satisfies both verifiers and whichever is tried first wins. The
        assembly puts `HUMAN` first for that reason, and a row asserts it — a
        `FederatedVerifier` built the other way round would label people as machines.
        """
        if self._subject_kind is SubjectKind.HUMAN and looks_like_a_machine_credential(claims):
            raise AuthenticationRefused(
                "this credential was issued to a client with no person present, and this "
                "surface accepts human identities here",
                reason_code="subject_kind_mismatch",
            )

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

        self._require_declared_kind(claims)

        # After signature, issuer, audience and tenant — so an unreachable mapping store
        # cannot be probed with a token this surface would have refused anyway.
        roles = resolve_roles(claims, self._mappings_source())
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
        # Below `no_tenant` on purpose. A federated pair tries both members, so a person's
        # token missing its tenant refuses `no_tenant` from one and `subject_kind_mismatch`
        # from the other — and the caller needs to hear about the tenant, which is the
        # fault, rather than about a verifier that was never going to accept it.
        "subject_kind_mismatch": 2,
        "expired_identity": 3,
        "idp_unreachable": 4,
        "unverifiable_identity": 5,
        "absent_identity": 6,
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
    "IdentityVerifier",
    "TokenVerifier",
]
