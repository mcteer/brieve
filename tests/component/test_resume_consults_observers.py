# SPDX-License-Identifier: Apache-2.0
"""Re-observation asks the tool's own observer, and believes it (014 T019, FR-006).

The question this answers is the one a checkpoint cannot: a step whose intent was written and
whose result was not may or may not have taken effect, and only the product knows. Assuming
either direction is a defect — assuming it happened drops work, assuming it did not repeats a
non-repeatable effect.

**The assertion is that the observer was CALLED**, not merely that a decision emerged. A
resume that reached the right conclusion without consulting anything would pass a
decision-only assertion and be wrong for every input the fixture did not cover.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.durability.memory import InMemoryDurabilityProvider
from core.durability.resume import ResumeDecision, resume_run
from core.durability.types import CheckpointBlob, IntentRecord
from core.observation.types import ObservationOutcome
from core.run import RunState
from tests.harness import ScriptedObserver, durability_grant, fake_identity_fabric, frozen_clock


def _interrupted(tool_name: str = "vault_write") -> tuple[InMemoryDurabilityProvider, str]:
    """A run holding one open intent — an effect begun and unaccounted for."""
    provider = InMemoryDurabilityProvider()
    key = f"run-1:1:{tool_name}"
    provider.record_intent(
        IntentRecord(
            run_id="run-1",
            idempotency_key=key,
            step_index=1,
            tool_name=tool_name,
            recorded_at=datetime.now(UTC),
        )
    )
    return provider, key


def _resume(
    provider: InMemoryDurabilityProvider, observers: dict[str, Any], **kw: Any
) -> ResumeDecision:
    clock = frozen_clock()
    grant = durability_grant(clock, tool_names={"vault_write"})
    provider.save(CheckpointBlob(blob_id="run-1", grant_id=grant.grant_id, step_index=0))
    provider.save_grant(grant)
    return resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(
            subject_user_id=grant.subject_user_id,
            tool_names={"vault_write"},
            ceiling_tools={"vault_write"},
        ),
        clock=clock,
        observers=observers,
        **kw,
    )


def test_the_open_intents_own_observer_is_the_one_consulted() -> None:
    """FR-006: *that* observer, chosen by tool name, and actually called.

    Two observers registered, one intent. Consulting the wrong one is the failure the double
    bracket used to guarantee: until 014 the entrypoint's loop recorded every intent as
    `"echo"` regardless of what ran, so a Vault write was re-observed by asking about echo.
    """
    provider, key = _interrupted("vault_write")
    right = ScriptedObserver(default=ObservationOutcome.HAPPENED)
    wrong = ScriptedObserver(default=ObservationOutcome.DID_NOT_HAPPEN)

    decision = _resume(provider, {"vault_write": right, "echo": wrong})

    assert right.calls == [key], "the tool's own observer was not asked about its intent"
    assert wrong.calls == [], "an unrelated observer was consulted"
    assert [i.step_index for i in decision.completed_steps] == [1]


def test_happened_marks_the_step_completed() -> None:
    """The effect landed, so the step must not run again."""
    provider, _ = _interrupted()

    decision = _resume(
        provider, {"vault_write": ScriptedObserver(default=ObservationOutcome.HAPPENED)}
    )

    assert decision.state is RunState.ACTIVE
    assert [i.step_index for i in decision.completed_steps] == [1]
    assert decision.pending_steps == []


def test_did_not_happen_leaves_the_step_pending() -> None:
    """The effect did not land, so the step must run.

    The direction a completion-only assertion cannot see: a resume that wrongly skipped here
    would exit successfully having dropped the work.
    """
    provider, _ = _interrupted()

    decision = _resume(
        provider, {"vault_write": ScriptedObserver(default=ObservationOutcome.DID_NOT_HAPPEN)}
    )

    assert decision.state is RunState.ACTIVE
    assert [i.step_index for i in decision.pending_steps] == [1]
    assert decision.completed_steps == []


def test_cannot_determine_suspends_naming_the_product() -> None:
    """The only suspension, and it names what the health checker watches.

    `depends_on` maps the tool to its product. Without it the suspension carries the TOOL
    name, and the sweeper — which watches products — never matches a recovery to it. That run
    waits forever, which is the hang the mechanism exists to prevent.
    """
    provider, _ = _interrupted("terraform_apply")
    grant_tools = {"terraform_apply"}
    clock = frozen_clock()
    grant = durability_grant(clock, tool_names=grant_tools)
    provider.save(CheckpointBlob(blob_id="run-1", grant_id=grant.grant_id, step_index=0))
    provider.save_grant(grant)

    decision = resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(
            subject_user_id=grant.subject_user_id,
            tool_names=grant_tools,
            ceiling_tools=grant_tools,
        ),
        clock=clock,
        observers={"terraform_apply": ScriptedObserver()},
        depends_on={"terraform_apply": "terraform"},
    )

    assert decision.state is RunState.SUSPENDED
    assert decision.awaiting == "terraform", "the product, never the tool name"
