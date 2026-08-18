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

from collections.abc import Iterator
from typing import Any

import pytest

from core.authority.vault_fabric import SubjectScopedVaultFabric, VaultIdentityFabric
from core.durability.credentials import (
    NomadWorkloadIdentity,
    VaultDatabaseCredentials,
)
from core.registry.memory import ToolRegistry
from surfaces.toolset import (
    AUTHORING_VOCABULARY,
    build_registry,
    known_actions,
    known_tools,
)
from tests.harness.operator_credentials import OperatorCredentials

#: What this platform can do, as the ceiling records name it — **derived from a registry**,
#: not declared. The fixture definitions in `infra/environments/dev/variables.tf` are
#: authored against exactly these, so a literal here that drifted from what registered would
#: make a correct ceiling record refuse `unknown_ceiling_entry` against the LIVE fabric,
#: and the error would name the ceiling rather than this file.
_VOCABULARY_REGISTRY = build_registry()[0]
KNOWN_TOOLS = known_tools(_VOCABULARY_REGISTRY) | AUTHORING_VOCABULARY
KNOWN_ACTIONS = known_actions(_VOCABULARY_REGISTRY)


def production_fabric(**kwargs: object) -> VaultIdentityFabric:
    """A real fabric, authenticating as the conformance workload."""
    return VaultIdentityFabric(
        credentials=VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance"),
        known_tools=KNOWN_TOOLS,
        known_actions=KNOWN_ACTIONS,
        **kwargs,
    )


def registry_of_known_tools() -> ToolRegistry:
    """Every tool the ceiling records may name, so none of them is an unknown entry.

    The shared builder rather than re-registering names in a loop, which is what this did
    before 013. Re-registering by name dropped every product binding, so `product_actions()`
    came back empty and any product-shaped ceiling refused — a defect this lane never saw
    because it read `KNOWN_ACTIONS` from a literal instead of from the registry.
    """
    return build_registry()[0]


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
