# SPDX-License-Identifier: Apache-2.0
"""Shared construction for the identity rows.

**The Vault role is the thing to get right here**, and it is easy to get wrong in a way
that reads as a configuration problem. These rows run inside the conformance allocation,
whose workload identity carries ``nomad_job_id = "conformance"``. Asking for the default
``harness`` role fails as::

    error validating claims: claim "nomad_job_id" does not match any associated bound
    claim values

which names the claim rather than the role, and sends a reader to the JWT auth config
instead of to the one argument that is wrong. 008 hit the same shape at T030; the durability
and api conftests already pass ``role="conformance"`` for the same reason, and this file
exists so the identity rows do not each rediscover it.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest

from core.authority.vault_fabric import SubjectScopedVaultFabric, VaultIdentityFabric
from core.durability.credentials import (
    DatabaseCredential,
    NomadWorkloadIdentity,
    VaultDatabaseCredentials,
)
from core.registry.memory import ToolRegistry

#: What this platform can do, as the ceiling records name it. The fixture definitions in
#: `infra/environments/dev/variables.tf` are authored against exactly these.
KNOWN_TOOLS = frozenset({"echo", "plan", "apply"})
KNOWN_ACTIONS = frozenset({"product.workspace.read", "product.workspace.write"})


def production_fabric(**kwargs: object) -> VaultIdentityFabric:
    """A real fabric, authenticating as the conformance workload."""
    return VaultIdentityFabric(
        credentials=VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance"),
        known_tools=KNOWN_TOOLS,
        known_actions=KNOWN_ACTIONS,
        **kwargs,
    )


def registry_of_known_tools() -> ToolRegistry:
    """Every tool the ceiling records may name, so none of them is an unknown entry."""
    registry = ToolRegistry()
    for name in sorted(KNOWN_TOOLS):
        registry.register(name, lambda _arguments: {"ok": "ran"})
    return registry


def subject_fabric(*roles: str) -> SubjectScopedVaultFabric:
    """A **fully** production fabric bound to a subject's roles.

    Every term — ceiling, user scope, policy — resolves from the live trust fabric. This
    replaced a hybrid that delegated one resolution to the real fabric and the rest to the
    fake, which existed only because the four stories had to be provable before all four
    landed. They have landed, so it is gone (T046a): scaffolding that survives its purpose
    becomes the next feature's precedent.
    """
    return SubjectScopedVaultFabric(
        roles=roles,
        credentials=VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance"),
        known_tools=KNOWN_TOOLS,
        known_actions=KNOWN_ACTIONS,
    )


@pytest.fixture
def fabric() -> VaultIdentityFabric:
    return production_fabric()


class OperatorCredentials:
    """Postgres credentials for a **host** process holding the operator's Vault token.

    **This is deliberately test-only, and deliberately not a second `WorkloadIdentity`.**
    Nothing in `src/` authenticates with a static token — Principle IV, and the reason
    `NomadWorkloadIdentity` raises rather than falling back when no identity is present.
    A class in `core.durability` that accepted a token would make that fallback available
    to production by import, which is how a test affordance becomes a deployment.

    It exists because the divergence rows genuinely belong on the host: they drive the
    scheduler, which the allocation cannot. The `make conformance` comment already names
    this lane as the one that "holds an admin token the allocation deliberately lacks" —
    and reading the trail as an operator is exactly the posture of the investigator the
    row serves. It is not pretending to be an attested workload; it is the other thing.
    """

    def __init__(self, creds_path: str = "database/creds/harness") -> None:
        self._addr = (os.environ.get("VAULT_ADDR") or "http://127.0.0.1:8200").rstrip("/")
        self._creds_path = creds_path
        cacert = os.environ.get("VAULT_CACERT")
        self._ssl = ssl.create_default_context(cafile=cacert) if cacert else None
        # Both names, because the two are the same secret under different conventions:
        # `VAULT_TOKEN` is what the Vault CLI reads, and `VAULT_ROOT_TOKEN` is what
        # `make dev-up` writes to `.env`. Reading only the CLI name would make this row
        # pass for whoever had just used the CLI and fail for everyone else, which is the
        # least useful way for a gate row to be unreliable.
        token = os.environ.get("VAULT_TOKEN") or os.environ.get("VAULT_ROOT_TOKEN")
        if not token:
            pytest.fail(
                "the divergence rows read the trail as an operator and neither "
                "VAULT_TOKEN nor VAULT_ROOT_TOKEN is set. `make conformance` passes it "
                "from .env; a bare pytest invocation needs it exported. Not skippable — "
                "a row that skips itself reports the same green as one that ran."
            )
        self._token = token

    def fetch(self) -> Any:
        request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
            f"{self._addr}/v1/{self._creds_path}", headers={"X-Vault-Token": self._token}
        )
        with urllib.request.urlopen(request, timeout=10, context=self._ssl) as response:  # noqa: S310
            body = json.loads(response.read())
        data = body["data"]
        return DatabaseCredential(
            username=data["username"],
            password=data["password"],
            # Carried, not invented: the lease is what makes this credential expire, and a
            # placeholder here would be a credential nothing could revoke.
            lease_id=str(body.get("lease_id") or ""),
        )


@pytest.fixture
def operator_credentials() -> OperatorCredentials:
    """What both accounts are read under, so neither is read more privileged than the other."""
    return OperatorCredentials()


@pytest.fixture
def trail_connection(operator_credentials: OperatorCredentials) -> Iterator[Any]:
    """A raw connection for reading the audit trail directly.

    **Deliberately not named `run_connection`**, which is what the divergence rows first
    asked for. A fixture by that name exists in `tests/conformance/api/conftest.py` — but
    conftests do not cross sibling packages, so the rows collected with an *error* rather
    than a failure, and an erroring row reports nothing about the thing it guards. Worse,
    the api one is a connection *factory*; had the name resolved, the rows would have
    called `.cursor()` on a function. Two fixtures sharing a name and not a shape is a
    trap that springs the first time someone moves a file, so this one has its own name.

    Raw, like the evidence rows: the divergence check compares what the trail *stores*
    against what the index stores, and going through a query object would compare two
    readers rather than two accounts.
    """
    import pg8000.dbapi

    cred = operator_credentials.fetch()
    conn = pg8000.dbapi.connect(
        host="127.0.0.1",
        port=5432,
        database="brieve",
        user=cred.username,
        password=cred.password,
    )
    yield conn
    try:
        conn.close()
    except Exception:  # noqa: BLE001 — a close failure must not mask the row's own result
        pass
