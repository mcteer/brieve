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

import pytest

from core.authority.vault_fabric import SubjectScopedVaultFabric, VaultIdentityFabric
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
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
