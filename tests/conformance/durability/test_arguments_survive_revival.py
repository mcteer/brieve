# SPDX-License-Identifier: Apache-2.0
"""040 — a revived step re-invokes with what the model asked for (M7, M8, M12).

**This file exists to prevent one specific stub**, and the stub is unusually available here.
`InMemoryDurabilityProvider` stores the `IntentRecord` object itself, so a new field on that
record round-trips **for free** — a revival row proven against it alone passes whether or not
the SQL was ever widened. `core/durability/memory.py` states the rule in its own words:
*"The two must agree here or a row proven against one says nothing about the other — and this
is precisely the property a hermetic row would be used to prove."*

**It lives beside the other durability rows on purpose.** This directory's `conftest` already
parameterises every row over both providers, fails rather than skips when the enclave is
absent, and hands out per-invocation run ids. A second fixture doing roughly the same thing is
how two provider setups drift until one of them stops meaning anything.

`test_the_in_memory_provider_cannot_prove_the_column` asserts the asymmetry itself rather than
describing it — if the in-memory store ever stops carrying a new field for free, the
parameterisation above has lost its reason and somebody should know.
"""

from __future__ import annotations

from typing import Any

from core.authority.grant import DelegationGrant
from core.authority.types import AuthorityScope
from core.choice.bounded import resolve_step_tool
from core.choice.chooser import Answer, ChoiceRequest
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import IntentRecord
from core.registry.memory import ToolRegistry
from core.run import GovernedRun, start_governed_run
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    capture_audit,
    durability_grant,
    fake_identity_fabric,
    frozen_clock,
)

#: These rows resolve authority through the identity fake to hold everything except the durable
#: store constant. What varies here is the PROVIDER; a row that also varied identity would not
#: be measuring the store.
FAKE_FABRIC_IS_FAULT_INJECTION = "identity and ceiling held constant to isolate the durable store"

#: What the model asked for. Non-trivial on purpose: a single-key request would pass against an
#: implementation that carried only the first argument, and `cas` is the one `vault_write`
#: raises without — the same reason 014 put it in the probe constant.
THE_REQUEST: dict[str, Any] = {"path": "secret/data/app", "cas": 7, "note": "authored"}


class _Watching:
    """Records the arguments it was actually called with. That is the whole assertion."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, arguments: Any) -> Any:
        self.calls.append(dict(arguments))
        return {"ok": True}

    @property
    def seen(self) -> dict[str, Any]:
        assert self.calls, "the handler was never called"
        return self.calls[-1]


class _RecordingChooser:
    """Answers once, and counts. The count is M8's whole assertion."""

    def __init__(self, answer: Answer) -> None:
        self.answer = answer
        self.asked = 0

    def choose(self, request: ChoiceRequest) -> Answer:
        self.asked += 1
        return self.answer


def _durable_run(
    provider: Any, clock: Any, grant: DelegationGrant, run_id: str
) -> tuple[GovernedRun, _Watching]:
    registry = ToolRegistry()
    handler = _Watching()
    # Non-repeatable, so the call is bracketed — an intent before the effect is the subject.
    registry.register("provision", handler, repeatable=False)
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id=f"corr-{run_id}",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"provision"})),
        identity_fabric=fake_identity_fabric(tool_names={"provision"}, ceiling_tools={"provision"}),
        clock=clock,
        registry=registry,
        audit_sink=capture_audit(),
    )
    run.clock = clock
    run.run_id = run_id
    run.durability = provider
    run.grant = grant
    return run, handler


def test_row_m7_a_revived_step_reinvokes_with_the_models_request(
    provider: Any, run_id: str
) -> None:
    """M7, FR-004, SC-003 — against BOTH providers, and that clause is the row.

    A step runs with a model-supplied request, leaving an intent behind. The revival honours
    the recorded act — and honouring it means re-invoking with **the arguments the model
    chose**, not with an empty map. Before this feature the intent carried only a tool name,
    so there was nothing to re-invoke *with*.

    The standby chooser would answer differently if consulted, which is what makes "replayed
    the recorded act" distinguishable from "asked again and happened to agree".
    """
    clock = frozen_clock()
    grant = durability_grant(clock, tool_names={"provision"})
    run, _ = _durable_run(provider, clock, grant, run_id)

    resolve_step_tool(
        run,
        task="provision the thing",
        permitted=["provision"],
        step_index=0,
        model="fixture/scripted@1",
        chooser=_RecordingChooser(Answer("provision", THE_REQUEST)),
    )

    stored = provider.closed_intents(run_id) + provider.open_intents(run_id)
    assert [i.arguments for i in stored] == [THE_REQUEST], (
        "the intent must carry what the model asked for; without it a revival has nothing to "
        "repeat the act with"
    )

    revived, revived_handler = _durable_run(provider, clock, grant, f"{run_id}-revived")
    standby = _RecordingChooser(Answer("provision", {"path": "DIFFERENT", "cas": 999}))
    resolve_step_tool(
        revived,
        task="provision the thing",
        permitted=["provision"],
        step_index=0,
        model="fixture/scripted@1",
        chooser=standby,
        already_chosen=Answer(stored[0].tool_name, stored[0].arguments or {}),
    )

    assert revived_handler.seen == THE_REQUEST, (
        "the revival re-invoked with something other than the recorded request — repeating a "
        "DIFFERENT act while claiming to have observed the first is re-execution wearing "
        "observation's clothes"
    )
    assert standby.asked == 0, "M8: a revived step consults no model (FR-005, SC-004)"


def test_row_m12_a_pre_feature_record_revives_as_it_first_ran(provider: Any, run_id: str) -> None:
    """M12, FR-011, SC-008 — NULL is not empty.

    An intent written before the column existed carries no arguments, and its first attempt
    ran with the platform's pre-040 constant. Reviving it with `{}` would repeat a *different*
    act than the one attempted — the defect even when the different act is emptier — so the
    entrypoint substitutes the legacy values. This row pins the distinction at the record
    level, which is where it is decidable rather than guessable, and it pins it **through a
    round trip** so a store that flattened one into the other would be caught.
    """
    clock = frozen_clock()
    provider.record_intent(
        IntentRecord(
            run_id=run_id,
            step_index=0,
            tool_name="provision",
            idempotency_key=f"{run_id}:0:provision",
            recorded_at=clock.now(),
        )
    )
    provider.record_intent(
        IntentRecord(
            run_id=run_id,
            step_index=1,
            tool_name="provision",
            idempotency_key=f"{run_id}:1:provision",
            arguments={},
            recorded_at=clock.now(),
        )
    )

    by_step = {i.step_index: i for i in provider.open_intents(run_id)}
    assert by_step[0].arguments is None, "NULL means recorded before this feature existed"
    assert by_step[1].arguments == {}, "an empty map means a post-040 act that asked for nothing"
    assert by_step[0].arguments != by_step[1].arguments, (
        "the two must survive a round trip distinguishable — a revival reads NULL as 'run with "
        "the legacy constant' and {} as 'run with nothing', and they are different acts"
    )


def test_the_in_memory_provider_cannot_prove_the_column() -> None:
    """**Why every row above is parameterised**, asserted rather than described.

    The in-memory provider returns the object it was handed, so it carries a new field with no
    column, no serialisation, and no migration anywhere in the path. A revival row proven
    against it alone has proven nothing about the store production uses.
    """
    memory = InMemoryDurabilityProvider()
    record = IntentRecord(
        run_id="r",
        step_index=0,
        tool_name="provision",
        idempotency_key="r:0:provision",
        arguments=THE_REQUEST,
        recorded_at=frozen_clock().now(),
    )
    memory.record_intent(record)
    [back] = memory.open_intents("r")
    assert back is record, (
        "the in-memory provider no longer returns the same object it was handed. That is not "
        "necessarily wrong, but it was the reason these rows run against both providers — so "
        "whoever changed it should confirm the Postgres leg is still the one doing the proving"
    )
