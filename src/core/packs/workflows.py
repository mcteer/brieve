# SPDX-License-Identifier: Apache-2.0
"""Workflows and the tier that bounds them (ADR-0045).

**The manifest already declared `workflows[]` and nothing in the platform had a runtime
shape for one**, so competency tiers had nothing to bound and US5's refusal would have been
asserted against a concept that did not exist.

Deliberately minimal. A workflow here is a *named, tiered thing a definition may or may not
run*, which is all ADR-0045 needs; what a workflow actually **does** is pack content, and
giving it an execution model in `core` would be the core learning about products by a
different route.

**Tiers bound workflows, never tools.** The ceiling answers "may this agent call `apply`?"
and the tier answers "may this agent *compose*?" — two mechanisms answering one question is
the duplication ADR-0044 forbids, and they would eventually disagree. That disjointness is
asserted: a tier change never alters which tools are reachable.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The lowest tier. Paved paths only — a definition here follows golden paths and composes
#: nothing. Least privilege applied to *capability* rather than to credentials.
TIER_PAVED = 1


@dataclass(frozen=True)
class WorkflowRecord:
    """A workflow a definition may run, and the tier it takes to run it."""

    name: str
    minimum_tier: int
    #: Whether this is a fully-paved golden path. A lower-tier definition may run only
    #: paved workflows — `minimum_tier` alone is not enough, because a workflow could
    #: declare a low tier without being paved and would then be reachable from a tier whose
    #: whole meaning is "paved paths only".
    paved: bool
    pack: str

    def permitted_for(self, tier: int) -> bool:
        """Whether a definition at this tier may run this workflow.

        Two conditions, and the second is the one a `minimum_tier >= tier` check alone
        would miss: at `TIER_PAVED` the definition is confined to paved paths regardless of
        what a workflow declares its minimum to be.
        """
        if tier < self.minimum_tier:
            return False
        return self.paved if tier <= TIER_PAVED else True


def resolve_workflow(
    workflows: dict[str, WorkflowRecord], name: str, *, tier: int
) -> WorkflowRecord:
    """Return the workflow, or refuse `above_tier` / `unknown_workflow`.

    Raises:
        AboveTierError: the definition's tier does not permit this workflow.
        KeyError: no such workflow in any pack the definition reaches.
    """
    record = workflows.get(name)
    if record is None:
        raise KeyError(name)
    if not record.permitted_for(tier):
        raise AboveTierError(
            f"workflow {name!r} requires tier {record.minimum_tier} "
            f"({'paved' if record.paved else 'unpaved'}); definition is tier {tier}",
            reason_code="above_tier",
        )
    return record


class AboveTierError(Exception):
    """A composition the definition's tier forbids.

    **The tier wins over the request**, always. It is a property of the definition,
    reviewable at design time like any other part of it — never something the person asking
    can raise by asking differently.
    """

    def __init__(self, message: str, *, reason_code: str = "above_tier") -> None:
        super().__init__(message)
        self.reason_code = reason_code


__all__ = ["TIER_PAVED", "AboveTierError", "WorkflowRecord", "resolve_workflow"]
