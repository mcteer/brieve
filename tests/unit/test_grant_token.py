# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — the token a grant becomes (016 T018).

Two things these rows exist for. The claim set must match what Vault's schema requires,
because the failure when it does not is a bare `403` whose reason lives only in Vault's
server log — the least diagnosable failure in this feature. And **no key material may appear
anywhere in this module's inputs, outputs, or call arguments**, because a signing key held
outside Vault would be the second standing credential Principle IV does not permit.
"""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from core.authority.grant_token import (
    AUDIENCE,
    DEFAULT_ISSUER,
    DEFAULT_KEY_ID,
    GrantTokenError,
    build_signing_input,
    sign_grant_token,
)

ISSUED = datetime(2026, 7, 31, 12, 0, 0, tzinfo=UTC)
EXPIRES = ISSUED + timedelta(hours=8)
DETAILS = [{"type": "vault:path_access", "path": "secret/data/planner/*", "capabilities": ["read"]}]


def _decode(segment: str) -> dict[str, Any]:
    padded = segment + "=" * (-len(segment) % 4)
    decoded: dict[str, Any] = json.loads(base64.urlsafe_b64decode(padded))
    return decoded


def _parts(**overrides: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    kwargs: dict[str, Any] = {
        "subject": "planner-agent",
        "authorization_details": DETAILS,
        "issued_at": ISSUED,
        "expires_at": EXPIRES,
    }
    kwargs.update(overrides)
    header, payload = build_signing_input(**kwargs).split(".")
    return _decode(header), _decode(payload)


def test_the_header_names_es256_and_the_key_vault_trusts() -> None:
    """ES256 is forced by transit's JWS marshaling, not chosen."""
    header, _ = _parts()

    assert header == {"alg": "ES256", "typ": "JWT", "kid": DEFAULT_KEY_ID}


def test_every_claim_vaults_schema_requires_is_present() -> None:
    """The absent-claim failure is a bare 403 with the reason only in Vault's log."""
    _, claims = _parts()

    assert set(claims) >= {"iss", "aud", "sub", "jti", "iat", "nbf", "exp", "authorization_details"}
    assert claims["iss"] == DEFAULT_ISSUER
    assert claims["aud"] == AUDIENCE
    assert claims["sub"] == "planner-agent"


def test_jti_is_always_present_and_never_repeats() -> None:
    """Mandatory, and the single hardest failure here to diagnose without this row."""
    _, first = _parts()
    _, second = _parts()

    assert first["jti"] and second["jti"]
    assert first["jti"] != second["jti"], (
        "a repeated jti is a replay identifier that identifies nothing"
    )


def test_nbf_precedes_iat_so_a_token_is_usable_the_instant_it_is_minted() -> None:
    """Vault compares against its own clock; same-instant tokens otherwise read as future."""
    _, claims = _parts()

    assert claims["nbf"] < claims["iat"]
    assert claims["exp"] == int(EXPIRES.timestamp())


def test_the_authorization_details_travel_unchanged() -> None:
    """This module transcribes Vault's format; it does not translate into one."""
    _, claims = _parts()

    assert claims["authorization_details"] == DETAILS


def test_an_empty_scope_is_a_valid_token_that_reaches_nothing() -> None:
    """A task entailing no resource access gets a grant, not an error (spec Edge Cases)."""
    _, claims = _parts(authorization_details=[])

    assert claims["authorization_details"] == []


def test_signing_asks_vault_and_holds_no_key_material() -> None:
    """GATE:no-secret-leak — the whole argument for transit over a local key.

    Asserts on what crosses the boundary: the call carries a path and a base64 signing input
    and nothing else. A private key, a PEM, or a passphrase appearing here would mean the
    issuing service held one.
    """
    seen: list[tuple[str, dict[str, Any]]] = []

    def fake_write(path: str, payload: dict[str, Any]) -> dict[str, Any]:
        seen.append((path, payload))
        return {"data": {"signature": "vault:v1:c2lnbmF0dXJl"}}

    token = sign_grant_token(signing_input="aGVhZGVy.cGF5bG9hZA", vault_write=fake_write)

    ((path, payload),) = seen
    assert path == "task-authority/sign/grant-issuer"
    assert set(payload) == {"input", "hash_algorithm", "marshaling_algorithm"}
    assert payload["marshaling_algorithm"] == "jws", "ASN.1 is not something JWS can read"
    blob = json.dumps({"path": path, "payload": payload, "token": token}).lower()
    for forbidden in ("private", "begin ec", "begin rsa", "passphrase", "-----begin"):
        assert forbidden not in blob, f"key material {forbidden!r} crossed the boundary"


def test_vaults_key_version_prefix_does_not_travel_into_the_token() -> None:
    """`vault:v1:` is Vault's rotation bookkeeping and means nothing to JWS."""
    token = sign_grant_token(
        signing_input="aGVhZGVy.cGF5bG9hZA",
        vault_write=lambda _p, _b: {"data": {"signature": "vault:v3:c2ln"}},
    )

    assert token == "aGVhZGVy.cGF5bG9hZA.c2ln"
    assert "vault:" not in token


def test_a_signing_failure_raises_rather_than_yielding_an_unsigned_token() -> None:
    """An unsigned grant is no grant, and returning one would be the fail-open direction."""

    def broken(_path: str, _payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("transit unreachable")

    with pytest.raises(GrantTokenError) as caught:
        sign_grant_token(signing_input="a.b", vault_write=broken)

    assert "could not be signed" in str(caught.value)
