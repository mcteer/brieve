# SPDX-License-Identifier: Apache-2.0
"""Pure effective-authority intersection algebra.

**The intersection answers *whether*; this module also answers *which term* (041).** Until
041 the algebra returned one set and nothing else, so every refusal downstream read
`authority_insufficient` — correct, and useless to an operator, because "your ceiling does not
carry this tool" and "this run asked for less than your ceiling allows" send a reader to two
different records. One is a governance change; the other is a dispatch fix.

The exclusion answer is computed here rather than at the deny site for the reason the
intersection itself lives here: it is the only place that has all the terms at once. A hook
holding the effective set alone cannot reconstruct which term dropped a name, and a second
implementation that tried would be a second answer to the same question.
"""

from __future__ import annotations

from collections.abc import Mapping

from core.authority.types import AuthorityScope

#: The definition's ceiling does not carry the tool. A governance record decides this, so the
#: operator reading it goes to the ceiling — not to whoever dispatched the run.
OUTSIDE_CEILING = "outside_ceiling"

#: The ceiling carries it and this run did not ask for it. Task scope may narrow the ceiling
#: (Principle IV: "task scope MAY narrow the ceiling; it is not required to"), so this is a
#: property of the dispatch rather than of the definition's authority.
OUTSIDE_TASK_SCOPE = "outside_task_scope"

#: The human on whose behalf the run acts does not hold it. `effective authority = user ∩
#: agent ceiling ∩ task scope ∩ policy`, and an agent never exceeds its human.
OUTSIDE_USER_SCOPE = "outside_user_scope"

#: Live policy narrowed it after issuance. Distinct from the three above because it can become
#: true mid-run, while the others are settled before the first step.
OUTSIDE_POLICY = "outside_policy"


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


def excluded_by(
    tool_name: str,
    *,
    user: AuthorityScope,
    ceiling: AuthorityScope,
    requested: AuthorityScope,
    policy: AuthorityScope | None = None,
) -> str | None:
    """Which term dropped ``tool_name``, or ``None`` when every term carries it.

    **Precedence is deliberate and is not "first failure wins by accident".** The order is
    user → ceiling → task scope → policy, from the most fundamental bound to the most local.
    When two terms both exclude a tool, the reported one is the bound a reader must satisfy
    *first*: widening a task scope to reach a tool the ceiling never carried is wasted work,
    and telling somebody to do it is worse than saying nothing.
    """
    if tool_name not in user.tool_names:
        return OUTSIDE_USER_SCOPE
    if tool_name not in ceiling.tool_names:
        return OUTSIDE_CEILING
    if tool_name not in requested.tool_names:
        return OUTSIDE_TASK_SCOPE
    if policy is not None and tool_name not in policy.tool_names:
        return OUTSIDE_POLICY
    return None


def exclusions(
    *,
    user: AuthorityScope,
    ceiling: AuthorityScope,
    requested: AuthorityScope,
    policy: AuthorityScope | None = None,
) -> Mapping[str, str]:
    """Every tool any term mentions but the intersection drops, mapped to the term that dropped it.

    Computed over the **union** of the terms rather than over the ceiling alone: a run that
    requests a tool no ceiling mentions must still get an answer naming the ceiling, and a
    ceiling naming a tool the user lacks must still name the user. Restricting the domain to
    one term would leave exactly the interesting cases unexplained.

    The result carries no secret and no authority — it is a map from a tool name to one of four
    fixed strings — so it is safe to hold on a run and to put in an audit payload.
    """
    effective = intersect_scopes(user, ceiling, requested, policy)
    mentioned = set(user.tool_names) | set(ceiling.tool_names) | set(requested.tool_names)
    if policy is not None:
        mentioned |= set(policy.tool_names)
    found: dict[str, str] = {}
    for name in mentioned - set(effective.tool_names):
        term = excluded_by(name, user=user, ceiling=ceiling, requested=requested, policy=policy)
        if term is not None:
            found[name] = term
    return found


def live_effective(
    issued: AuthorityScope,
    current_policy: AuthorityScope | None,
) -> AuthorityScope:
    """issued ∩ current_policy; None policy leaves issued unchanged."""
    if current_policy is None:
        return issued
    return issued.intersect(current_policy)


__all__ = [
    "OUTSIDE_CEILING",
    "OUTSIDE_POLICY",
    "OUTSIDE_TASK_SCOPE",
    "OUTSIDE_USER_SCOPE",
    "excluded_by",
    "exclusions",
    "intersect_scopes",
    "live_effective",
]
