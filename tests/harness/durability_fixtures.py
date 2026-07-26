# SPDX-License-Identifier: Apache-2.0
"""Durability test fixtures — grants, scriptable observers, disruption.

Disruption is simulated **in-process**: a run is torn down and rebuilt from its
checkpoint. That is deterministic and fast, and FR-016 forbids simulating disruption by
terminating real infrastructure. One scenario additionally crosses a genuine process
boundary (`test_resume_cross_process`), because an entirely in-process suite would
prove the code reloads its own state, not that the state survived anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from core.authority.clock import Clock
from core.authority.grant import DelegationGrant, issue_grant
from core.authority.types import AuthorityScope
from core.durability.types import CheckpointBlob, DurabilityProvider, RunOutcome
from core.observation.types import Observation, ObservationOutcome
from tests.harness.fake_identity_fabric import DEFAULT_AGENT_DEFINITION_ID


def durability_grant(
    clock: Clock,
    *,
    subject_user_id: str = "user-1",
    agent_definition_id: str = DEFAULT_AGENT_DEFINITION_ID,
    tool_names: set[str] | None = None,
    duration: timedelta = timedelta(hours=1),
) -> DelegationGrant:
    """A live grant for tests that need consent but do not care about its shape."""
    return issue_grant(
        subject_user_id=subject_user_id,
        agent_definition_id=agent_definition_id,
        requested_scope=AuthorityScope(tool_names=frozenset(tool_names or {"read_tool"})),
        clock=clock,
        duration=duration,
    )


@dataclass
class ScriptedObserver:
    """An observer whose answer the test chooses.

    Defaults to ``CANNOT_DETERMINE`` on purpose: a test that forgets to script an
    outcome should park, which is visible, rather than silently pick a direction.
    """

    outcomes: dict[str, ObservationOutcome] = field(default_factory=dict)
    default: ObservationOutcome = ObservationOutcome.CANNOT_DETERMINE
    raises: bool = False
    calls: list[str] = field(default_factory=list)

    def observe(self, *, idempotency_key: str) -> Observation:
        self.calls.append(idempotency_key)
        if self.raises:
            raise RuntimeError("external system unreachable")
        return Observation(outcome=self.outcomes.get(idempotency_key, self.default))


@dataclass
class SideEffectCounter:
    """Counts executions so 'exactly once across the whole run' is assertable.

    A per-segment counter would pass a broken implementation that re-runs completed
    steps after resume — the count has to span the disruption.
    """

    counts: dict[str, int] = field(default_factory=dict)

    def record(self, step: str) -> None:
        self.counts[step] = self.counts.get(step, 0) + 1

    def total(self, step: str) -> int:
        return self.counts.get(step, 0)


def write_checkpoint(
    provider: DurabilityProvider,
    *,
    blob_id: str,
    correlation_id: str,
    grant_id: str,
    step_index: int,
    written_by: str,
    payload: dict[str, object] | None = None,
    outcome: RunOutcome | None = None,
) -> CheckpointBlob:
    """Persist run state the way the invoke path does."""
    blob = CheckpointBlob(
        blob_id=blob_id,
        payload=dict(payload or {}),
        correlation_id=correlation_id,
        grant_id=grant_id,
        step_index=step_index,
        written_by=written_by,
        outcome=outcome,
    )
    provider.save(blob)
    return blob


def simulate_disruption(provider: DurabilityProvider) -> DurabilityProvider:
    """Model a process dying and a new allocation taking over.

    Returns the provider a *new* instance would see. For a durable store that is the
    same store; the point of the indirection is that the test never carries in-memory
    run state across the boundary by accident — which would prove nothing.
    """
    return provider
