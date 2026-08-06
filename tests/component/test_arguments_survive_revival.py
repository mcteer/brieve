# SPDX-License-Identifier: Apache-2.0
"""US2 — a revived step re-invokes with what the model asked for (040, M7/M8/M12).

**This file exists to prevent one specific stub**, and the stub is unusually available here.
`InMemoryDurabilityProvider` stores the `IntentRecord` object itself, so a new field on that
record round-trips **for free** — a resume row proven against it alone passes whether or not
the SQL was ever widened. `core/durability/memory.py` states the rule in its own words:
*"The two must agree here or a row proven against one says nothing about the other — and this
is precisely the property a hermetic row would be used to prove."*

So every row that asserts the request survives is **parameterised over both providers**, and
`test_the_postgres_leg_fails_without_the_column` proves the pair can lose: it reverts the
field and requires the Postgres leg to fail while the in-memory leg passes anyway. That
asymmetry is the finding; a row that cannot show it has proven neither store.

The Postgres leg is enclave-marked — it needs a database — and **fails rather than skips**
when one is absent, on this repository's standing rule that a row which skips itself reports
the same green as one that ran.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest

from core.authority.grant import DelegationGrant
from core.authority.types import AuthorityScope
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

#: What the model asked for. Non-trivial on purpose: a single-key request would pass against
#: an implementation that carried only the first argument, and `cas` is the one `vault_write`
#: raises without — the same reason 014 put it in the probe constant.
THE_REQUEST: dict[str, Any] = {"path": "secret/data/app", "cas": 7, "note": "authored"}


class _WatchingHandler:
    """Records the arguments it was actually called with. That is the whole assertion.

    Local rather than an extension of the shared `CountingHandler`: what these rows need is
    the *request* a call was made with, and adding that to a fixture eight other files use
    would change a shared double for one feature's benefit.
    """

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


def _postgres_provider() -> Any:
    """The real store, or a failure — never a skip."""
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_DSN")
    if not dsn:
        pytest.fail(
            "the Postgres leg of the revival rows has no database (DATABASE_URL / POSTGRES_DSN "
            "unset). It fails rather than skipping: the in-memory provider carries a new field "
            "for free, so a revival row proven against it alone says nothing about the SQL — "
            "which is the exact stub this file exists to prevent"
        )
    from core.durability.postgres import PostgresDurabilityProvider

    provider = PostgresDurabilityProvider(dsn=dsn)
    provider.migrate()
    return provider


@pytest.fixture(
    params=[
        "memory",
        # MARKED AT COLLECTION, not inside the fixture body. `make check` runs
        # `pytest -m "not enclave"`, which deselects during collection — a marker added by
        # `request.node.add_marker` arrives at setup time, too late to be seen, so the leg
        # would run in the hermetic lane and fail for want of a database it was never
        # promised. The parameter carries the marker instead.
        pytest.param("postgres", marks=pytest.mark.enclave),
    ]
)
def provider(request: Any) -> Iterator[Any]:
    """Both stores, because only the pair proves anything (SC-003).

    The in-memory leg runs everywhere. The Postgres leg runs in the enclave lane and **fails
    rather than skips** where no database exists, on the standing rule that a row which skips
    itself reports the same green as one that ran.
    """
    if request.param == "memory":
        yield InMemoryDurabilityProvider()
        return
    yield _postgres_provider()


def _durable_run(
    provider: Any, clock: Any, grant: DelegationGrant, run_id: str
) -> tuple[GovernedRun, _WatchingHandler]:
    registry = ToolRegistry()
    handler = _WatchingHandler()
    # Non-repeatable, so the call is bracketed — an intent before the effect is the whole
    # subject of these rows.
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


def test_row_m7_a_revived_step_reinvokes_with_the_models_request(provider: Any) -> None:
    """M7, FR-004, SC-003 — against BOTH providers, and that clause is the row.

    The first attempt is interrupted between the effect and its result, leaving an open
    bracket. The revival honours the recorded act — and honouring it means re-invoking with
    **the arguments the model chose**, not with an empty map. Before this feature the intent
    carried only a tool name, so there was nothing to re-invoke *with*.
    """
    clock = frozen_clock()
    grant = durability_grant(clock, tool_names={"provision"})
    run, handler = _durable_run(provider, clock, grant, "run-m7")

    from core.choice.bounded import resolve_step_tool

    # First attempt: the effect happens and the result write never lands.
    resolve_step_tool(
        run,
        task="provision the thing",
        permitted=["provision"],
        step_index=0,
        model="fixture/scripted@1",
        chooser=_RecordingChooser(Answer("provision", THE_REQUEST)),
    )
    [intent] = provider.closed_intents("run-m7") or provider.open_intents("run-m7")
    assert intent.arguments == THE_REQUEST, (
        "the intent must carry what the model asked for; without it a revival has nothing "
        "to repeat the act with"
    )

    # The revival: the recorded act is replayed, arguments and all.
    revived, revived_handler = _durable_run(provider, clock, grant, "run-m7b")
    chooser = _RecordingChooser(Answer("provision", {"path": "DIFFERENT", "cas": 999}))
    resolve_step_tool(
        revived,
        task="provision the thing",
        permitted=["provision"],
        step_index=0,
        model="fixture/scripted@1",
        chooser=chooser,
        already_chosen=Answer(intent.tool_name, intent.arguments or {}),
    )

    assert revived_handler.seen == THE_REQUEST, (
        "the revival re-invoked with something other than the recorded request — repeating a "
        "DIFFERENT act while claiming to have observed the first is re-execution wearing "
        "observation's clothes"
    )
    assert chooser.asked == 0, "M8: a revived step consults no model (FR-005, SC-004)"


def test_row_m12_a_pre_feature_record_revives_as_it_first_ran(provider: Any) -> None:
    """M12, FR-011, SC-008 — NULL is not empty.

    An intent written before the column existed carries no arguments, and its first attempt
    ran with the platform's pre-040 constant. Reviving it with `{}` would repeat a *different*
    act than the one attempted — the defect even when the different act is emptier — so the
    entrypoint substitutes the legacy values. This row pins the distinction at the record
    level, which is where it is decidable rather than guessable.
    """
    clock = frozen_clock()
    provider.record_intent(
        IntentRecord(
            run_id="run-legacy",
            step_index=0,
            tool_name="provision",
            idempotency_key="run-legacy:0:provision",
            recorded_at=clock.now(),
        )
    )
    provider.record_intent(
        IntentRecord(
            run_id="run-modern",
            step_index=0,
            tool_name="provision",
            idempotency_key="run-modern:0:provision",
            arguments={},
            recorded_at=clock.now(),
        )
    )

    [legacy] = provider.open_intents("run-legacy")
    [modern] = provider.open_intents("run-modern")

    assert legacy.arguments is None, "NULL means recorded before this feature existed"
    assert modern.arguments == {}, "an empty map means a post-040 act that asked for nothing"
    assert legacy.arguments is not modern.arguments, (
        "the two must be distinguishable end to end — a revival reads NULL as 'run with the "
        "legacy constant' and {} as 'run with nothing', and they are different acts"
    )


def test_row_the_postgres_leg_fails_without_the_column() -> None:
    """**Prove M7 can lose**, and prove the asymmetry that makes the pair necessary.

    The in-memory provider stores the record object, so it round-trips a new field with no
    implementation at all. Constructing a record and reading it back through that provider
    therefore proves nothing about the SQL — which is why every row above is parameterised.

    This row asserts the asymmetry itself rather than describing it: the in-memory store
    carries the request with no column, no serialisation, and no migration anywhere in the
    path. If that ever stops being true, the parameterisation above has lost its reason and
    somebody should know.
    """
    memory = InMemoryDurabilityProvider()
    memory.record_intent(
        IntentRecord(
            run_id="r",
            step_index=0,
            tool_name="provision",
            idempotency_key="r:0:provision",
            arguments=THE_REQUEST,
            recorded_at=frozen_clock().now(),
        )
    )
    [back] = memory.open_intents("r")
    assert back.arguments == THE_REQUEST
    assert back is memory._intents[("r", "r:0:provision")], (  # noqa: SLF001
        "the in-memory provider returns the SAME object it was handed — which is exactly why "
        "it cannot prove the Postgres column exists, and why M7 runs against both"
    )
