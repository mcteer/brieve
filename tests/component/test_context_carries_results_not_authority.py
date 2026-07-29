# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — what a later turn receives is results, never authority.

ADR-0042: cached or precedent results never carry authority; every requester runs their own
token exchange, scope check, and approvals. A thread is where that rule is easiest to break
by accident, because "carry the last run's context forward" sounds like it might reasonably
include the grant that run held.

It does not. A carried result is the recorded output under the reserved key, and nothing
else from the checkpoint travels — not the grant id, not the credential, not the scope.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob
from core.threads.context import RESULT_KEY, resolve_run_input
from core.threads.records import RunInput
from core.threads.store import InMemoryThreadStore


def _checkpoint_with_everything(durability: InMemoryDurabilityProvider, run_id: str) -> None:
    """A realistic terminal checkpoint: the result, plus everything else it carries."""
    durability.save(
        CheckpointBlob(
            blob_id=run_id,
            payload={
                RESULT_KEY: {"plan": "survey then apply"},
                # Resume state, which lives in the same payload and must not travel.
                "step": 7,
                "framework_state": {"messages": ["internal"]},
            },
            correlation_id=run_id,
            grant_id="grant-abc-123",
            step_index=7,
            written_by="alloc-9",
        )
    )


def test_only_the_result_travels() -> None:
    store, durability = InMemoryThreadStore(), InMemoryDurabilityProvider()
    _checkpoint_with_everything(durability, "run-earlier")
    store.put_run_input(
        RunInput(
            run_id="run-later",
            message="continue",
            context_run_ids=("run-earlier",),
            created_at=datetime.now(UTC),
        )
    )

    resolved = resolve_run_input(run_id="run-later", store=store, durability=durability)

    assert resolved is not None
    carried = resolved.context[0][1]
    assert "survey then apply" in carried
    # Resume state is not context. A later run receiving another run's framework state
    # would be inheriting its execution, not its output.
    assert "framework_state" not in carried
    assert "internal" not in carried
    assert '"step"' not in carried


def test_no_grant_or_credential_material_reaches_a_later_run() -> None:
    """The ADR-0042 assertion, stated as an absence a row can check."""
    store, durability = InMemoryThreadStore(), InMemoryDurabilityProvider()
    _checkpoint_with_everything(durability, "run-earlier")
    store.put_run_input(
        RunInput(
            run_id="run-later",
            message="continue",
            context_run_ids=("run-earlier",),
            created_at=datetime.now(UTC),
        )
    )

    resolved = resolve_run_input(run_id="run-later", store=store, durability=durability)

    assert resolved is not None
    everything = resolved.message + "".join(body for _rid, body in resolved.context)
    for forbidden in ("grant-abc-123", "grant_id", "credential", "token", "alloc-9"):
        assert forbidden not in everything, (
            f"authority-shaped material {forbidden!r} travelled with a carried result"
        )


def test_a_result_that_itself_contains_a_secret_shaped_key_still_travels_verbatim() -> None:
    """The honest limit of this guarantee, asserted so it is not misread.

    This rule is about the platform not *adding* authority to context. It is not a
    redaction pass over what a run chose to put in its own result — a run that writes a
    credential into its result has already leaked it into the checkpoint, and that is a
    problem about the run rather than about threads. Recorded here so the next reader does
    not assume a filter exists.
    """
    store, durability = InMemoryThreadStore(), InMemoryDurabilityProvider()
    durability.save(
        CheckpointBlob(
            blob_id="run-earlier",
            payload={RESULT_KEY: {"note": "the token is abc"}},
            correlation_id="run-earlier",
        )
    )
    store.put_run_input(
        RunInput(
            run_id="run-later",
            message="continue",
            context_run_ids=("run-earlier",),
            created_at=datetime.now(UTC),
        )
    )

    resolved = resolve_run_input(run_id="run-later", store=store, durability=durability)

    assert resolved is not None
    assert "the token is abc" in resolved.context[0][1]
