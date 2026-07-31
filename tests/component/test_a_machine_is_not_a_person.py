# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a machine's credential does not become a person.

Two failures in one, and the second is worse than the first. The surface **declared** what
kind of subject its tokens established, at construction, and asserted it for every token
it accepted. So a `client_credentials` token was:

1. recorded as a human being, which makes the evidence trail wrong about who acted; and
2. **accepted**, which made a leaked client secret a working operator login that the trail
   showed as somebody signing in.

The rows below are about tokens a real provider actually issues. Auth0's machine token
carries `gty: client-credentials`, `azp: <client id>` and `sub: <client id>@clients` — all
three observed on a live tenant, not invented for the test — and a person's carries none
of them.
"""

from __future__ import annotations

import pytest

from core.identity.claims import ClaimMapping
from core.identity.kind import looks_like_a_machine_credential
from core.identity.types import SubjectKind
from surfaces.api.verification import (
    AuthenticationRefused,
    FederatedVerifier,
    TokenVerifier,
)
from tests.harness.fake_oidc_provider import AUDIENCE, ISSUER, FakeOIDCProvider

CLIENT_ID = "FFJe9KJvlNpSrYOWZ0OJwf1EveyapIzp"
MAPPINGS = [ClaimMapping(claim_name="groups", claim_value="platform", role="operator")]


@pytest.fixture
def idp() -> FakeOIDCProvider:
    return FakeOIDCProvider()


def verifier(idp: FakeOIDCProvider, kind: SubjectKind = SubjectKind.HUMAN) -> TokenVerifier:
    return TokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        mappings=MAPPINGS,
        key_loader=lambda: {idp.key_id: idp.jwks_public_key()},
        subject_kind=kind,
    )


def machine_token(idp: FakeOIDCProvider, **extra: object) -> str:
    """The shape Auth0 issues for `client_credentials`, as observed on a live tenant."""
    claims = {
        "groups": ["platform"],
        "gty": "client-credentials",
        "azp": CLIENT_ID,
        **extra,
    }
    return idp.token(subject=f"{CLIENT_ID}@clients", claims=claims)


def person_token(idp: FakeOIDCProvider) -> str:
    return idp.token(subject="alice@example.test", claims={"groups": ["platform"]})


# --------------------------------------------------------------- the evidence itself


def test_the_grant_type_is_evidence() -> None:
    assert looks_like_a_machine_credential({"gty": "client-credentials", "sub": "anything"})


def test_a_subject_naming_its_own_client_is_evidence() -> None:
    """RFC 9068 §2.2 — with no resource owner, `sub` identifies the client."""
    assert looks_like_a_machine_credential({"azp": CLIENT_ID, "sub": CLIENT_ID})
    assert looks_like_a_machine_credential({"azp": CLIENT_ID, "sub": f"{CLIENT_ID}@clients"})
    assert looks_like_a_machine_credential({"client_id": CLIENT_ID, "sub": CLIENT_ID})


def test_a_person_using_a_client_is_not_evidence() -> None:
    """`azp` is on a person's token too — it names the app they signed in through.

    The distinction is whether `sub` is that same client. Treating the mere presence of
    `azp` as machine-ness would refuse every human token from a provider that sets it,
    which is most of them.
    """
    assert not looks_like_a_machine_credential({"azp": CLIENT_ID, "sub": "auth0|alice"})


def test_a_lookalike_subject_is_not_evidence() -> None:
    """Anchored on the client id, so a person whose id merely starts similarly is safe."""
    assert not looks_like_a_machine_credential({"azp": "abc", "sub": "abcdef"})


def test_a_bare_workload_token_carries_no_evidence() -> None:
    """A Nomad workload identity has none of these markers, and is still a machine.

    This is why the verifier's check is asymmetric. Demanding a marker before believing
    a `WORKLOAD` declaration would refuse every genuine federated workload, whose issuer
    serves nothing else and whose declaration is therefore the evidence.
    """
    assert not looks_like_a_machine_credential({"sub": "api", "nomad_job_id": "api"})


# ------------------------------------------------------------------ the refusal


def test_a_human_surface_refuses_a_machine_credential(idp: FakeOIDCProvider) -> None:
    """The security half. A leaked client secret is not a login."""
    with pytest.raises(AuthenticationRefused) as refusal:
        verifier(idp).verify(machine_token(idp))

    assert refusal.value.reason_code == "subject_kind_mismatch"


def test_the_refusal_is_not_about_the_signature(idp: FakeOIDCProvider) -> None:
    """The token is perfectly valid. It is the wrong KIND, and must say so.

    An operator who sees `unverifiable_identity` goes to look at keys and algorithms; the
    machine token's signature, issuer and audience are all correct and they would find
    nothing.
    """
    with pytest.raises(AuthenticationRefused) as refusal:
        verifier(idp).verify(machine_token(idp))

    assert refusal.value.reason_code != "unverifiable_identity"
    assert "no person present" in str(refusal.value)


def test_a_person_is_still_admitted(idp: FakeOIDCProvider) -> None:
    """The control. A check that refused everyone would pass every row above."""
    subject = verifier(idp).verify(person_token(idp))

    assert subject.subject_kind is SubjectKind.HUMAN
    assert subject.subject_user_id == "alice@example.test"


def test_a_workload_verifier_admits_it_and_labels_it_a_machine(idp: FakeOIDCProvider) -> None:
    subject = verifier(idp, SubjectKind.WORKLOAD).verify(machine_token(idp))

    assert subject.subject_kind is SubjectKind.WORKLOAD


# ------------------------------------------- one issuer serving both kinds (Auth0)


@pytest.fixture
def both(idp: FakeOIDCProvider) -> FederatedVerifier:
    """The production shape: one issuer, one audience, one JWKS, two kinds.

    Human FIRST — see below. This is the arrangement `service.py` builds.
    """
    return FederatedVerifier(
        [verifier(idp, SubjectKind.HUMAN), verifier(idp, SubjectKind.WORKLOAD)]
    )


def test_one_issuer_still_tells_them_apart(idp: FakeOIDCProvider, both: FederatedVerifier) -> None:
    """The case a per-verifier declaration cannot handle, and the reason for all of this.

    Auth0, Okta, Ping and Entra all serve `client_credentials` and `authorization_code`
    from the same issuer. Nothing about WHERE the token came from distinguishes them.
    """
    assert both.verify(person_token(idp)).subject_kind is SubjectKind.HUMAN
    assert both.verify(machine_token(idp)).subject_kind is SubjectKind.WORKLOAD


def test_order_decides_when_only_one_member_discriminates(idp: FakeOIDCProvider) -> None:
    """Why the assembly puts HUMAN first, asserted rather than left as a comment.

    The workload verifier admits a person's token — it has to, because a bare workload
    identity carries no marker either. So with a shared issuer, a person's token satisfies
    both members and the first one tried wins. Built the other way round, people are
    recorded as machines.
    """
    wrong_way = FederatedVerifier(
        [verifier(idp, SubjectKind.WORKLOAD), verifier(idp, SubjectKind.HUMAN)]
    )

    assert wrong_way.verify(person_token(idp)).subject_kind is SubjectKind.WORKLOAD, (
        "if this ever fails the risk is gone and this row should be deleted — until then "
        "it documents why order is load-bearing"
    )


def test_a_real_fault_is_reported_over_a_kind_mismatch(idp: FakeOIDCProvider) -> None:
    """A person's token with no tenant must say `no_tenant`, not `subject_kind_mismatch`.

    Both members refuse it, for different reasons, and only one of them is the fault.
    Reporting the kind mismatch would send an operator to look at grant types over a
    missing claim.
    """
    tokenless_tenant = idp.token(
        subject="alice@example.test", claims={"groups": ["platform"]}, tenant=""
    )

    with pytest.raises(AuthenticationRefused) as refusal:
        FederatedVerifier(
            [verifier(idp, SubjectKind.WORKLOAD), verifier(idp, SubjectKind.HUMAN)]
        ).verify(tokenless_tenant)

    assert refusal.value.reason_code == "no_tenant"
