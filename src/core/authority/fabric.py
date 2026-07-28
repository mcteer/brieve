# SPDX-License-Identifier: Apache-2.0
"""Identity fabric protocol — how a governed run learns what it is allowed to do.

Four resolutions, and after 010 they come from the control-plane trust fabric rather than
from a test double. The protocol says nothing about which, deliberately: the fake survives
for fault injection, and a protocol that named its production implementation would make
injecting a fault a special case rather than an ordinary one.

**What is NOT here matters as much as what is.** This protocol used to declare
``issue_brokered_material`` and ``get_brokered_material``, whose own docstrings said "(fake
only)". A production implementation would have been obliged to implement two methods that
existed for tests, and the honest implementation is a pair that raise — a protocol
admitting it does not describe its own production case. They are gone, and the check that
keeps them gone is ``tests/unit/test_protocol_has_no_test_affordances.py``.

Every method refuses by raising rather than returning a default. **No failure path returns
an empty scope**: an empty scope is a legitimate answer meaning "this principal may do
nothing", and it must stay distinguishable from "the platform could not find out". One is
a permissions decision and the other is an outage.
"""

from __future__ import annotations

from typing import Protocol

from core.authority.types import AuthorityScope


class IdentityFabric(Protocol):
    """Resolve user scope, agent ceiling, policy, and product entitlements."""

    def resolve_user_scope(self, subject_user_id: str) -> AuthorityScope:
        """Return the requesting user's harness-domain scope."""
        ...

    def resolve_ceiling(self, agent_definition_id: str) -> AuthorityScope:
        """Return the ceiling for this agent definition.

        Ceilings are per-definition: an unknown id resolves to unavailable or
        refuses, never to an open ceiling.
        """
        ...

    def resolve_policy(self, agent_definition_id: str) -> AuthorityScope | None:
        """Return current policy scope for this definition, or None for unrestricted."""
        ...

    def resolve_product_entitlements(self, subject_user_id: str, product: str) -> frozenset[str]:
        """Return the user's product-domain action entitlements."""
        ...
