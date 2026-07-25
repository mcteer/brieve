# SPDX-License-Identifier: Apache-2.0
"""Pure effective-authority intersection algebra."""

from __future__ import annotations

from core.authority.types import AuthorityScope


def intersect_scopes(
    user: AuthorityScope,
    ceiling: AuthorityScope,
    requested: AuthorityScope,
    policy: AuthorityScope | None = None,
) -> AuthorityScope:
    """Return user ∩ ceiling ∩ requested ∩ policy (policy None = unrestricted)."""
    effective = AuthorityScope(
        tool_names=user.tool_names & ceiling.tool_names & requested.tool_names,
        product_actions=user.product_actions & ceiling.product_actions & requested.product_actions,
    )
    if policy is None:
        return effective
    return effective.intersect(policy)


def live_effective(
    issued: AuthorityScope,
    current_policy: AuthorityScope | None,
) -> AuthorityScope:
    """issued ∩ current_policy; None policy leaves issued unchanged."""
    if current_policy is None:
        return issued
    return issued.intersect(current_policy)
