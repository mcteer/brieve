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

from core.authority.vault_fabric import VaultIdentityFabric
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.registry.memory import ToolRegistry
from tests.harness import fake_identity_fabric
from tests.harness.hybrid_fabric import HybridIdentityFabric

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


def hybrid(*real_terms: str) -> HybridIdentityFabric:
    """Real for the named terms, faked for the rest. Deleted at T046a.

    See `tests/harness/hybrid_fabric.py`: `manufacture_authority` resolves scope, ceiling,
    and policy from one object, so proving one term before the others exist requires
    composing them.
    """
    return HybridIdentityFabric(
        real=production_fabric(),
        fake=fake_identity_fabric(
            tool_names=set(KNOWN_TOOLS),
            product_actions=set(KNOWN_ACTIONS),
            ceiling_tools=set(KNOWN_TOOLS),
            ceiling_actions=set(KNOWN_ACTIONS),
        ),
        real_terms=frozenset(real_terms),
    )


@pytest.fixture
def fabric() -> VaultIdentityFabric:
    return production_fabric()
