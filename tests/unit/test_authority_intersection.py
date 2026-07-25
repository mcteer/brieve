# SPDX-License-Identifier: Apache-2.0
"""Intersection algebra and equality-at-bound."""

from __future__ import annotations

from core.authority.intersection import intersect_scopes, live_effective
from core.authority.types import AuthorityScope


def test_intersection_narrows() -> None:
    user = AuthorityScope(
        tool_names=frozenset({"a", "b"}),
        product_actions=frozenset({"x", "y"}),
    )
    ceiling = AuthorityScope(
        tool_names=frozenset({"a", "c"}),
        product_actions=frozenset({"x"}),
    )
    requested = AuthorityScope(
        tool_names=frozenset({"a"}),
        product_actions=frozenset({"x"}),
    )
    eff = intersect_scopes(user, ceiling, requested, None)
    assert eff.tool_names == frozenset({"a"})
    assert eff.product_actions == frozenset({"x"})


def test_equality_at_bound_issues() -> None:
    bound = AuthorityScope(tool_names=frozenset({"a"}), product_actions=frozenset({"p"}))
    eff = intersect_scopes(bound, bound, bound, None)
    assert eff == bound
    assert bound.issubset(bound)


def test_live_effective_policy_shrink() -> None:
    issued = AuthorityScope(
        tool_names=frozenset({"a", "b"}),
        product_actions=frozenset({"p", "q"}),
    )
    policy = AuthorityScope(tool_names=frozenset({"a"}), product_actions=frozenset({"p"}))
    live = live_effective(issued, policy)
    assert live.tool_names == frozenset({"a"})
    assert live.product_actions == frozenset({"p"})
