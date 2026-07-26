# SPDX-License-Identifier: Apache-2.0
"""What the platform learned by re-reading external state.

A **new core package rather than part of the durability seam**: re-observation is a
harness guarantee (FR-006, FR-012), and putting it behind the provider interface would
let a provider decide whether resume re-observes at all.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class ObservationOutcome(StrEnum):
    """Three-way, deliberately.

    A two-way outcome would force a guess in exactly the case where guessing is the
    failure: replaying risks a duplicate infrastructure change, skipping risks a
    silently incomplete run, and only evidence distinguishes them.
    """

    HAPPENED = "happened"
    DID_NOT_HAPPEN = "did_not_happen"
    CANNOT_DETERMINE = "cannot_determine"


class Observation(BaseModel):
    """The recorded answer, and the basis for it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: ObservationOutcome
    detail: str = ""


class Observer(Protocol):
    """Supplied by the tool author, because only they know how to look.

    Kept on the tool registration rather than in a central table, which would drift
    from the tools it describes.
    """

    def observe(self, *, idempotency_key: str) -> Observation:
        """Re-read external state for the step identified by this key.

        An implementation that cannot reach the external system MUST return
        ``CANNOT_DETERMINE`` rather than assuming either outcome.
        """
        ...
