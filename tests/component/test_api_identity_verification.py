# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — what the verifier accepts, and everything it must refuse.

A verifier is judged by its refusals. Accepting a well-formed token proves almost nothing;
the failures below are the ones that fail *open* when got wrong, which means they pass
every naive test because legitimate tokens still work.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.identity.claims import ClaimMapping
from core.identity.types import SubjectKind
from surfaces.api.verification import AuthenticationRefused, TokenVerifier
from tests.harness.fake_oidc_provider import AUDIENCE, ISSUER, FakeOIDCProvider

MAPPINGS = [ClaimMapping(claim_name="groups", claim_value="platform", role="operator")]


@pytest.fixture
def idp() -> FakeOIDCProvider:
    return FakeOIDCProvider()


@pytest.fixture
def verifier(idp: FakeOIDCProvider) -> TokenVerifier:
    return TokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        mappings=MAPPINGS,
        key_loader=lambda: {idp.key_id: idp.jwks_public_key()},
    )


def _token(idp: FakeOIDCProvider, **kw: object) -> str:
    kw.setdefault("claims", {"groups": ["platform"]})
    return idp.token(**kw)  # type: ignore[arg-type]


def test_valid_identity_becomes_the_subject(idp: FakeOIDCProvider, verifier: TokenVerifier) -> None:
    subject = verifier.verify(_token(idp, subject="alice"))
    assert subject.subject_user_id == "alice"
    assert subject.tenant_id == "tenant-test"
    assert subject.roles == frozenset({"operator"})
    assert subject.subject_kind is SubjectKind.HUMAN


@pytest.mark.parametrize(
    ("maker", "reason"),
    [
        ("expired_token", "expired_identity"),
        ("not_yet_valid_token", "unverifiable_identity"),
        ("wrong_issuer_token", "unverifiable_identity"),
        ("wrong_audience_token", "unverifiable_identity"),
        ("wrong_key_token", "unverifiable_identity"),
    ],
)
def test_refuses_bad_identities(
    idp: FakeOIDCProvider, verifier: TokenVerifier, maker: str, reason: str
) -> None:
    token = getattr(idp, maker)(claims={"groups": ["platform"]})
    with pytest.raises(AuthenticationRefused) as exc:
        verifier.verify(token)
    assert exc.value.reason_code == reason


def test_refuses_alg_none(idp: FakeOIDCProvider, verifier: TokenVerifier) -> None:
    """The attack the pinned algorithm list exists to stop.

    A verifier reading the algorithm from the token's own header accepts this happily and
    still verifies every legitimate token, so nothing else in this file would catch it.
    """
    with pytest.raises(AuthenticationRefused):
        verifier.verify(idp.unsigned_token())


def test_refuses_absent_identity(verifier: TokenVerifier) -> None:
    for empty in (None, "", "   "):
        with pytest.raises(AuthenticationRefused) as exc:
            verifier.verify(empty)
        assert exc.value.reason_code == "absent_identity"


def test_refuses_unmapped_claims_distinguishably(
    idp: FakeOIDCProvider, verifier: TokenVerifier
) -> None:
    """An unmapped claim is not a default role — and says so differently from a bad token.

    Both refuse. Without distinct reason codes an operator debugging an integration cannot
    tell "your token is bad" from "your claim is not mapped".
    """
    with pytest.raises(AuthenticationRefused) as exc:
        verifier.verify(idp.token(claims={"groups": ["some-other-team"]}))
    assert exc.value.reason_code == "unmapped_claim"


def test_refuses_a_token_with_no_tenant(idp: FakeOIDCProvider, verifier: TokenVerifier) -> None:
    with pytest.raises(AuthenticationRefused) as exc:
        verifier.verify(idp.token(tenant=None, claims={"groups": ["platform"]}))
    assert exc.value.reason_code == "no_tenant"


def test_fails_closed_when_the_provider_is_unreachable(idp: FakeOIDCProvider) -> None:
    """Cold cache plus an unreachable provider refuses (FR-016)."""

    def _unreachable() -> dict[str, object]:
        raise ConnectionError("idp down")

    verifier = TokenVerifier(
        issuer=ISSUER, audience=AUDIENCE, mappings=MAPPINGS, key_loader=_unreachable
    )
    with pytest.raises(AuthenticationRefused) as exc:
        verifier.verify(_token(idp))
    assert exc.value.reason_code == "idp_unreachable"


def test_cached_keys_survive_a_provider_blip_but_expiry_still_applies(
    idp: FakeOIDCProvider,
) -> None:
    """Keys are public material and may be cached; identities are not and may not.

    Conflating the two is what makes FR-016 look self-contradictory. A shared outage must
    not become thousands of individual failures — but no token outlives its own `exp`.
    """
    calls = {"n": 0}

    def _loader() -> dict[str, object]:
        calls["n"] += 1
        if calls["n"] > 1:
            raise ConnectionError("idp down")
        return {idp.key_id: idp.jwks_public_key()}

    verifier = TokenVerifier(
        issuer=ISSUER, audience=AUDIENCE, mappings=MAPPINGS, key_loader=_loader
    )
    assert verifier.verify(_token(idp, subject="alice")).subject_user_id == "alice"

    # Provider is now down. A valid unexpired token still verifies from cached keys...
    assert verifier.verify(_token(idp, subject="bob")).subject_user_id == "bob"

    # ...but an expired one does not, cache or no cache.
    with pytest.raises(AuthenticationRefused) as exc:
        verifier.verify(
            idp.expired_token(claims={"groups": ["platform"]}),
        )
    assert exc.value.reason_code == "expired_identity"


def test_list_valued_claims_match_per_element(
    idp: FakeOIDCProvider, verifier: TokenVerifier
) -> None:
    subject = verifier.verify(idp.token(claims={"groups": ["other", "platform"]}))
    assert subject.roles == frozenset({"operator"})


def test_expiry_is_carried_onto_the_subject(idp: FakeOIDCProvider, verifier: TokenVerifier) -> None:
    subject = verifier.verify(_token(idp, lifetime=timedelta(minutes=7)))
    assert subject.expires_at is not None


def test_a_mapping_source_is_consulted_per_verification(idp: FakeOIDCProvider) -> None:
    """A mapping that clears quorum must take effect without a deploy.

    Captured at construction, the approval would sit inert until someone restarted the
    surface — which makes "whoever remembers to bounce the service" the second half of
    the quorum mechanism.
    """
    granted: list[ClaimMapping] = []
    verifier = TokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        mappings_source=lambda: list(granted),
        key_loader=lambda: {idp.key_id: idp.jwks_public_key()},
    )

    with pytest.raises(AuthenticationRefused) as refusal:
        verifier.verify(_token(idp))
    assert refusal.value.reason_code == "unmapped_claim"

    granted.extend(MAPPINGS)

    assert verifier.verify(_token(idp)).roles == frozenset({"operator"})


def test_a_revoked_mapping_stops_granting_without_a_restart(idp: FakeOIDCProvider) -> None:
    granted = list(MAPPINGS)
    verifier = TokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        mappings_source=lambda: list(granted),
        key_loader=lambda: {idp.key_id: idp.jwks_public_key()},
    )
    assert verifier.verify(_token(idp)).roles == frozenset({"operator"})

    granted.clear()

    with pytest.raises(AuthenticationRefused) as refusal:
        verifier.verify(_token(idp))
    assert refusal.value.reason_code == "unmapped_claim"


def test_literal_mappings_and_a_source_are_a_contradiction(idp: FakeOIDCProvider) -> None:
    """Not merged. A caller that passed both meant one, and would get neither."""
    with pytest.raises(ValueError, match="not both"):
        TokenVerifier(
            issuer=ISSUER,
            audience=AUDIENCE,
            mappings=MAPPINGS,
            mappings_source=lambda: [],
            key_loader=lambda: {idp.key_id: idp.jwks_public_key()},
        )
