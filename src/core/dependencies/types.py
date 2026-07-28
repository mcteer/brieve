# SPDX-License-Identifier: Apache-2.0
"""What the platform believes about the products agents operate.

Not about Vault, Postgres, or the scheduler — those failing is a different class of
problem, and one this mechanism could not help with anyway, since it needs them to record
anything at all.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class HealthState(StrEnum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    #: Never checked, or checked so long ago the answer is not worth trusting.
    UNKNOWN = "unknown"

    def permits_calls(self) -> bool:
        """Only ``HEALTHY`` permits a call.

        ``UNKNOWN`` is treated as unhealthy, which is the whole posture in one line:
        guessing reachable is how a dead dependency gets called anyway, and this mechanism
        exists to stop exactly that.
        """
        return self is HealthState.HEALTHY


class DenialClass(StrEnum):
    """Two kinds of "no", and blurring them trains the wrong behaviour.

    A **policy** denial is the governance boundary holding. An agent that treats it as an
    obstacle to route around inverts Principles II and III, so it is never surfaced to the
    model as something to adapt to.

    An **availability** denial invites a legitimate alternative: write the Terraform, hand
    it back, say the workspace was unreachable. That is a competent response, and this is
    the only class the model is told about.

    Getting this backwards would be invisible — everything would still work — while
    teaching agents that refusals are obstacles rather than boundaries.
    """

    POLICY = "policy"
    AVAILABILITY = "availability"

    def is_model_visible(self) -> bool:
        return self is DenialClass.AVAILABILITY


class DependencyHealth(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Named as the tool registry names it. Not per-workspace: that would mean the checker
    #: enumerating a customer's estate rather than asking whether a product answers.
    product: str
    state: HealthState
    #: So staleness is visible rather than inferred.
    checked_at: datetime
    #: Drives recovery hysteresis — several consecutive successes before healthy.
    consecutive_successes: int = 0
    #: What failed, for an operator. Never a credential.
    detail: str = ""


class DependencyHealthReader(Protocol):
    """What a run consults. **Read-only by construction.**

    There is no method here that records health, and that absence is the point: a run that
    could mark a dependency healthy is a run that could talk itself past a refusal. The
    health checker writes; everything else reads what it wrote (FR-006a).
    """

    def state_of(self, product: str) -> HealthState:
        """Current belief about this product. ``UNKNOWN`` when never checked or stale."""
        ...


__all__ = [
    "DenialClass",
    "DependencyHealth",
    "DependencyHealthReader",
    "HealthState",
]
