# SPDX-License-Identifier: Apache-2.0
"""Identity fabric protocol — fakes implement; core never calls a live IdP."""

from __future__ import annotations

from typing import Protocol

from core.authority.types import AuthorityScope


class IdentityFabric(Protocol):
    """Resolve user/ceiling/policy/entitlements and hold brokered material in-process."""

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

    def issue_brokered_material(self, credential_id: str, marker: str) -> None:
        """Store brokered secret-class material keyed by credential_id (fake only)."""
        ...

    def get_brokered_material(self, credential_id: str) -> str | None:
        """Return brokered material for tests; never for audit/spans."""
        ...
