# SPDX-License-Identifier: Apache-2.0
"""Single-writer run lease with fencing (FR-009, ADR-0026).

The requirement is that a partitioned instance's writes are **rejected, not merely
raced**. That is why the lease compares *identity* rather than timing: a superseded
allocation presents a superseded identity, and rejecting it is a comparison whose
answer does not depend on who got there first.

Under ADR-0048 this is largely a property of the substrate — a resumed run is a new
Nomad allocation with a new identity, so the zombie is holding something that provably
is not current. This module's job is to make that fact load-bearing rather than
incidental.
"""

from __future__ import annotations

from core.durability.types import DurabilityProvider
from core.errors import CoreError


class LeaseSupersededError(CoreError):
    """This instance no longer holds the run; another has resumed it.

    Distinct from an ordinary denial on purpose: an operator reading the audit trail
    needs to tell "a policy refused this" from "you are a zombie". They have very
    different remedies.
    """

    def __init__(
        self,
        message: str = "run lease superseded by another instance",
        *,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, correlation_id=correlation_id)
        self.reason_code = "lease_superseded"


class RunLease:
    """Acquire and check the single-writer claim on a run."""

    def __init__(self, provider: DurabilityProvider, *, run_id: str, holder_identity: str) -> None:
        if not holder_identity.strip():
            # A blank identity would compare equal to another blank one, which would
            # silently disable fencing for every anonymous writer.
            raise ValueError("holder_identity must be non-empty: fencing compares identities")
        self._provider = provider
        self.run_id = run_id
        self.holder_identity = holder_identity

    def acquire(self) -> None:
        self._provider.acquire_lease(self.run_id, self.holder_identity)

    def held(self) -> bool:
        return bool(self._provider.check_lease(self.run_id, self.holder_identity))

    def assert_held(self, *, correlation_id: str | None = None) -> None:
        """Raise if this instance has been superseded.

        Called before every tool call and every checkpoint write. Fail-closed: a
        provider error propagates rather than being read as "still held".
        """
        if not self.held():
            raise LeaseSupersededError(correlation_id=correlation_id)
