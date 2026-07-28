# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — machines federate; there is nothing else to present."""

from __future__ import annotations

import pytest

from core.identity.types import SubjectKind
from surfaces.api.verification import (
    AuthenticationRefused,
    FederatedVerifier,
    TokenVerifier,
)
from tests.harness.api_fixtures import DEFAULT_MAPPINGS
from tests.harness.fake_oidc_provider import AUDIENCE, ISSUER, FakeOIDCProvider

WORKLOAD_ISSUER = "https://workload.test.invalid/"


@pytest.fixture
def federated() -> tuple[FederatedVerifier, FakeOIDCProvider, FakeOIDCProvider]:
    human_idp = FakeOIDCProvider()
    workload_idp = FakeOIDCProvider(issuer=WORKLOAD_ISSUER)
    verifier = FederatedVerifier(
        [
            TokenVerifier(
                issuer=ISSUER,
                audience=AUDIENCE,
                mappings=DEFAULT_MAPPINGS,
                key_loader=lambda: {human_idp.key_id: human_idp.jwks_public_key()},
                subject_kind=SubjectKind.HUMAN,
            ),
            TokenVerifier(
                issuer=WORKLOAD_ISSUER,
                audience=AUDIENCE,
                mappings=DEFAULT_MAPPINGS,
                key_loader=lambda: {workload_idp.key_id: workload_idp.jwks_public_key()},
                subject_kind=SubjectKind.WORKLOAD,
            ),
        ]
    )
    return verifier, human_idp, workload_idp


def test_a_machine_authenticates_by_federated_identity(
    federated: tuple[FederatedVerifier, FakeOIDCProvider, FakeOIDCProvider],
) -> None:
    verifier, _, workload_idp = federated
    subject = verifier.verify(
        workload_idp.token(subject="svc-deployer", claims={"groups": ["platform"]})
    )
    assert subject.subject_kind is SubjectKind.WORKLOAD
    assert subject.subject_user_id == "svc-deployer"


def test_a_human_still_authenticates(
    federated: tuple[FederatedVerifier, FakeOIDCProvider, FakeOIDCProvider],
) -> None:
    verifier, human_idp, _ = federated
    subject = verifier.verify(human_idp.token(subject="alice", claims={"groups": ["platform"]}))
    assert subject.subject_kind is SubjectKind.HUMAN


def test_an_unknown_issuer_is_refused_by_both(
    federated: tuple[FederatedVerifier, FakeOIDCProvider, FakeOIDCProvider],
) -> None:
    verifier, human_idp, _ = federated
    with pytest.raises(AuthenticationRefused):
        verifier.verify(human_idp.wrong_issuer_token(claims={"groups": ["platform"]}))


def test_the_reported_refusal_is_the_most_specific_one(
    federated: tuple[FederatedVerifier, FakeOIDCProvider, FakeOIDCProvider],
) -> None:
    """A token that verified but mapped to no role must say so.

    Without this, the workload verifier rejecting the issuer would mask the human
    verifier's real finding, and an operator would be told their token was unverifiable
    when it was in fact fine and simply unmapped. That sends them to debug the wrong thing.
    """
    verifier, human_idp, _ = federated
    with pytest.raises(AuthenticationRefused) as exc:
        verifier.verify(human_idp.token(claims={"groups": ["not-mapped"]}))
    assert exc.value.reason_code == "unmapped_claim"
