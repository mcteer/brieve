# SPDX-License-Identifier: Apache-2.0
"""Reactive credential refresh — FR-017b, T011d.

The database's rejection is the signal, not a clock. The retry is bounded on purpose:
an unbounded one would spin against a genuine misconfiguration, and one is reachable in
the dev enclave (destroy the Postgres volume and every credential fails auth).
"""

from __future__ import annotations

import psycopg
import pytest

from core.durability.credentials import (
    CredentialUnavailableError,
    DatabaseCredential,
    NomadWorkloadIdentity,
)
from core.durability.postgres import DurabilityStoreError, PostgresDurabilityProvider


class FakeCredentials:
    def __init__(self) -> None:
        self.fetches = 0

    def fetch(self) -> DatabaseCredential:
        self.fetches += 1
        # Positional: the 002 fixture gate bans credential-shaped keyword literals in
        # unit tests, and it is right to — see tests/unit/test_core_import.py.
        return DatabaseCredential(f"v-user-{self.fetches}", "unused", f"lease-{self.fetches}")


class FakeConn:
    def __init__(self, fail_with: Exception | None) -> None:
        self._fail_with = fail_with

    def __enter__(self) -> FakeConn:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, *args: object, **kwargs: object) -> FakeConn:
        if self._fail_with is not None:
            raise self._fail_with
        return self

    def fetchone(self) -> None:
        return None


def _auth_error() -> psycopg.OperationalError:
    exc = psycopg.OperationalError("password authentication failed")
    exc.sqlstate = "28P01"
    return exc


def _network_error() -> psycopg.OperationalError:
    exc = psycopg.OperationalError("connection refused")
    exc.sqlstate = "08006"
    return exc


def _provider(
    creds: FakeCredentials, failures: list[Exception | None]
) -> PostgresDurabilityProvider:
    calls = iter(failures)

    def connect(**_: object) -> FakeConn:
        return FakeConn(next(calls, None))

    return PostgresDurabilityProvider(credentials=creds, connect=connect)  # type: ignore[arg-type]


def test_auth_failure_triggers_one_refresh_and_succeeds() -> None:
    creds = FakeCredentials()
    provider = _provider(creds, [_auth_error(), None])

    provider.check_lease("run-1", "alloc-1")

    assert creds.fetches == 2, "expected exactly one refresh after the rejection"


def test_non_auth_error_does_not_fetch_a_new_credential() -> None:
    """A refused connection is not evidence the credential is stale."""
    creds = FakeCredentials()
    provider = _provider(creds, [_network_error(), None])

    with pytest.raises(DurabilityStoreError):
        provider.check_lease("run-1", "alloc-1")

    assert creds.fetches == 1


def test_second_auth_failure_surfaces_rather_than_looping() -> None:
    creds = FakeCredentials()
    provider = _provider(creds, [_auth_error(), _auth_error()])

    with pytest.raises(DurabilityStoreError):
        provider.check_lease("run-1", "alloc-1")

    assert creds.fetches == 2, "bounded: refreshed once, then surfaced"


def test_credential_repr_does_not_leak_the_password() -> None:
    cred = DatabaseCredential("v-user", "s3nt1nel-value", "l")
    assert "s3nt1nel-value" not in repr(cred)
    assert "redacted" in repr(cred)


def test_no_workload_identity_fails_closed() -> None:
    """No attested identity means no credential — never a fallback to a static one."""
    identity = NomadWorkloadIdentity(name="vault")
    with pytest.raises(CredentialUnavailableError) as excinfo:
        identity.jwt()
    assert "attested identity" in str(excinfo.value)
