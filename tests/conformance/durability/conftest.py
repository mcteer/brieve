# SPDX-License-Identifier: Apache-2.0
"""Provider parameterization for the durability rows (T070).

Every row runs against **both** providers. That is the executable form of ADR-0024's
central claim: swapping durability backends changes performance, never whether resume
re-authenticates or whether a checkpoint may hold a credential. If a row needed
rewriting per provider, the claim would be false and the seam drawn in the wrong place.

Postgres failures are loud, never skipped. A row that quietly passes without the real
store would report a guarantee nobody tested.
"""

from __future__ import annotations

import json
import os
import pathlib
import socket
import urllib.request
import uuid
from collections.abc import Iterator

import pytest

from core.durability.credentials import DatabaseCredential
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.postgres import PostgresDurabilityProvider
from core.durability.types import DurabilityProvider

PROVIDERS = ("memory", "postgres")


def _root_token_from_env_file() -> str:
    """Read the dev root token from the gitignored .env, so `make conformance` works
    after `make dev-up` without the developer exporting anything.

    Values in .env are quoted; passing the quotes through is a real trap (it made Vault
    reject the license with "error decoding version: expected integer" once already).
    """
    path = pathlib.Path(__file__).resolve().parents[3] / ".env"
    if not path.is_file():
        return ""
    for line in path.read_text().splitlines():
        if line.startswith("VAULT_ROOT_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def _enclave_reachable() -> bool:
    for host, port in (("127.0.0.1", 5432), ("127.0.0.1", 8200)):
        try:
            with socket.create_connection((host, port), timeout=1):
                pass
        except OSError:
            return False
    return True


class DevVaultCredentials:
    """Development-only credential source, for running the rows from a workstation.

    Deliberately **in test code, not in `src/`**. The supported path is the workload
    presenting its own Nomad identity; adding a token-based shortcut to
    ``VaultDatabaseCredentials`` would put a bypass of the attestation chain into the
    product to save a step in a test.

    Inside a Nomad allocation this class is unused — the real credentials module
    applies, and with it the real chain.
    """

    def __init__(self, *, addr: str | None = None, token: str | None = None) -> None:
        self._addr = (addr or os.environ.get("VAULT_ADDR") or "http://127.0.0.1:8200").rstrip("/")
        self._token = token or os.environ.get("VAULT_TOKEN") or _root_token_from_env_file()

    def fetch(self) -> DatabaseCredential:
        if not self._token:
            pytest.fail(
                "no VAULT_TOKEN for the development credential path, and no Nomad "
                "workload identity. Export VAULT_TOKEN from .env, or run the suite as "
                "a Nomad job (the supported path)."
            )
        request = urllib.request.Request(  # noqa: S310
            f"{self._addr}/v1/database/creds/harness",
            headers={"X-Vault-Token": self._token},
        )
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
            body = json.loads(response.read())
        data = body["data"]
        return DatabaseCredential(data["username"], data["password"], body.get("lease_id", ""))


@pytest.fixture
def run_id(request: pytest.FixtureRequest) -> str:
    """A distinct run id per test **per invocation**.

    Both halves matter, and each was found the hard way against Postgres while the
    in-memory provider stayed green:

    - Distinct per test, or one row's leftover state breaks another.
    - Distinct per invocation, or yesterday's run has already closed today's intents
      and a row asserts against work it did not do.

    Real runs do not share identity either, so this is also the more faithful shape.
    """
    return f"conformance-{request.node.name}-{uuid.uuid4().hex[:12]}"


@pytest.fixture(params=PROVIDERS)
def provider(request: pytest.FixtureRequest) -> Iterator[DurabilityProvider]:
    if request.param == "memory":
        yield InMemoryDurabilityProvider()
        return

    if not _enclave_reachable():
        pytest.fail(
            "durability conformance requires the local enclave — run `make dev-up`. "
            "These rows are not skippable: a row that passes without the real store "
            "reports a guarantee nobody tested."
        )

    store = PostgresDurabilityProvider(credentials=DevVaultCredentials())  # type: ignore[arg-type]
    store.migrate()
    yield store
