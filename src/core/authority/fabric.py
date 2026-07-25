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

    def resolve_ceiling(self) -> AuthorityScope:
        """Return the agent ceiling scope."""
        ...

    def resolve_policy(self) -> AuthorityScope | None:
        """Return current policy scope, or None for unrestricted."""
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
