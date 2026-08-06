# SPDX-License-Identifier: Apache-2.0
"""040 — a model says what to do, and everything around that fact stays put.

This file owns one claim: **what a model may answer widened, and nothing else moved.** It
lives beside the recording-driven suites it is forbidden to disturb — `test_a_model_chooses`,
`test_the_double_is_faithful`, `test_a_choice_is_governed` — because splitting them across
directories lets one be read without the other, and "the answer got wider" and "every existing
recording still means what it meant" are the two halves of the same guarantee.

**The rows most worth reading are the ones about absence.** M9 pins `TOOL_CHOSEN` to its exact
six keys and `PRE_DECISION` to hashes, because the trail's rule — *no model output beyond the
name* — was argued when it was written and this feature is the first thing to press on it. The
request now rests durably in exactly one place, and one place is a claim that has to be
measured against every other place rather than asserted about the one.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest

from core.audit.schema import AuditEventType
from core.authority.types import AuthorityScope
from core.choice.bounded import DEFAULT_RECHOICE_BOUND, resolve_step_tool
from core.choice.chooser import Answer, ChoiceOutcome, ChoiceRequest, MalformedAnswer
from core.durability.memory import InMemoryDurabilityProvider
from core.registry.memory import DEFAULT_REQUEST_BYTES, ToolRegistry
from core.run import GovernedRun, start_governed_run
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    capture_audit,
    durability_grant,
    fake_identity_fabric,
    frozen_clock,
)
from tests.harness.frozen_clock import FrozenClock

#: Why these rows resolve authority through the fake (the repo's own gate demands a reason).
#:
#: **The fault injected is the CEILING, held constant so the widened answer is the only
#: variable.** M2 needs a capability that is registered and outside this run's reach, and M17
#: needs the same to produce a governance denial beside a capability failure — neither is
#: reachable through the production fabric without standing up an estate whose ceilings differ
#: per row. What is under test here is what a model may *say*; holding identity and ceiling
#: fixed is what keeps the answer's widening the only thing these rows can be measuring.
FAKE_FABRIC_IS_FAULT_INJECTION = "a ceiling that omits a registered capability, held constant"

#: A request with a value nobody should ever find in the trail. If this string turns up in an
#: audit payload, a row below has caught the regression its whole section exists for.
THE_REQUEST: dict[str, Any] = {"path": "secret/data/app", "cas": 4, "note": "MODEL-WROTE-THIS"}

SENTINEL = "MODEL-WROTE-THIS"


class _Watching:
    """A handler that records what it was called with."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, arguments: Any) -> Any:
        self.calls.append(dict(arguments))
        return {"ok": True}


class _Answers:
    """Replays answers, one per ask, and raises `MalformedAnswer` for a marker."""

    def __init__(self, *answers: Answer | MalformedAnswer) -> None:
        self._answers = list(answers)
        self.asked = 0

    def choose(self, request: ChoiceRequest) -> Answer:
        self.asked += 1
        answer = self._answers[min(self.asked, len(self._answers)) - 1]
        if isinstance(answer, MalformedAnswer):
            raise answer
        return answer


def _run(
    *,
    tools: dict[str, Any] | None = None,
    permitted: set[str] | None = None,
    durable: bool = False,
) -> tuple[GovernedRun, dict[str, _Watching], Any]:
    """A governed run over one or more watching tools."""
    registry = ToolRegistry()
    handlers: dict[str, _Watching] = {}
    for name, kwargs in (tools or {"provision": {}}).items():
        handler = _Watching()
        handlers[name] = handler
        registry.register(name, handler, **kwargs)

    names = permitted if permitted is not None else set(handlers)
    clock = frozen_clock()
    sink = capture_audit()
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-040",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset(names)),
        identity_fabric=fake_identity_fabric(tool_names=set(handlers), ceiling_tools=names),
        clock=clock,
        registry=registry,
        audit_sink=sink,
    )
    run.clock = clock
    if durable:
        run.run_id = "run-040"
        run.durability = InMemoryDurabilityProvider()
        run.grant = durability_grant(clock, tool_names=set(handlers))
    return run, handlers, sink


def _resolve(run: GovernedRun, chooser: Any, **kwargs: Any) -> Any:
    return resolve_step_tool(
        run,
        task="do the thing",
        permitted=sorted(run.scope),
        step_index=0,
        model="fixture/scripted@1",
        chooser=chooser,
        **kwargs,
    )


# ----------------------------------------------------------------- the act is the model's


def test_row_m1_two_requests_two_different_acts() -> None:
    """M1, FR-001, SC-001 — two, because one proves nothing.

    A single act matching a single request is indistinguishable from a platform constant that
    happens to match. Two runs stating different targets, producing correspondingly different
    acts, is the smallest observation that rules the constant out.
    """
    first_run, first_handlers, _ = _run()
    _resolve(first_run, _Answers(Answer("provision", {"path": "alpha"})))

    second_run, second_handlers, _ = _run()
    _resolve(second_run, _Answers(Answer("provision", {"path": "beta"})))

    assert first_handlers["provision"].calls == [{"path": "alpha"}]
    assert second_handlers["provision"].calls == [{"path": "beta"}]


def test_row_m2_the_same_authority_decides_on_the_same_facts() -> None:
    """M2, FR-002, FR-003, SC-002 — argument provenance is the only difference.

    A model-directed act traverses the pipeline a platform-directed one traversed: same entry,
    same hooks, same records. And a capability outside the ceiling refuses identically whether
    the request came from a model or from anywhere else — because permission is decided on the
    NAME, and 040 changed what an answer *contains*, never what it *unlocks*.
    """
    run, handlers, sink = _run(tools={"provision": {}, "forbidden": {}}, permitted={"provision"})
    resolution = _resolve(run, _Answers(Answer("provision", THE_REQUEST)))
    assert resolution.executed
    assert handlers["provision"].calls == [THE_REQUEST]

    denied_run, denied_handlers, denied_sink = _run(
        tools={"provision": {}, "forbidden": {}}, permitted={"provision"}
    )
    denied = _resolve(denied_run, _Answers(Answer("forbidden", THE_REQUEST)))
    assert not denied.executed, "a capability outside the ceiling is refused"
    assert denied_handlers["forbidden"].calls == [], "and it never ran"

    kinds = {e.event_type for e in denied_sink.all_entries()}
    assert AuditEventType.PRE_DECISION in kinds, (
        "the refusal is decided by the hook pipeline and recorded there — a model stating a "
        "request must not create a second path to a decision"
    )


def test_row_m3_a_capability_that_takes_nothing_is_untouched() -> None:
    """M3, FR-012 — equivalence, not a before/after that has no *before* to run.

    A bare-name recording and a structured answer naming the same tool with `{}` are the same
    act. The real before/after guarantee is the unedited suites (M13); this row asserts the
    equivalence that guarantee rests on.
    """
    bare_run, bare_handlers, _ = _run()
    _resolve(bare_run, _Answers(Answer("provision")))

    structured_run, structured_handlers, _ = _run()
    _resolve(structured_run, _Answers(Answer("provision", {})))

    assert bare_handlers["provision"].calls == structured_handlers["provision"].calls == [{}]


# ------------------------------------------------------------------- the one durable home


def test_row_m9_the_request_rests_in_exactly_one_place() -> None:
    """M9, FR-006, SC-005 — *no-secret-leak*.

    The closures are **asserted, not inherited**. Each holds today because of somebody else's
    decision — `record_choice` keeps model output out of the trail, `redact_arguments` hashes
    every argument set, the observer interface takes a key and not a record — and a claim that
    holds by inheritance stops holding the moment they revisit it.
    """
    run, handlers, sink = _run(tools={"provision": {"repeatable": False}}, durable=True)
    _resolve(run, _Answers(Answer("provision", THE_REQUEST)))
    assert handlers["provision"].calls == [THE_REQUEST], "the act happened as asked"

    entries = sink.all_entries()
    assert entries, "the step recorded something"

    # THE TRAIL CARRIES NO ARGUMENT VALUES, anywhere, in any member.
    for entry in entries:
        rendered = json.dumps(entry.payload, default=str)
        assert SENTINEL not in rendered, (
            f"{entry.event_type} carries a model-supplied argument VALUE. The append-only "
            f"trail is the one place a leaked secret cannot be taken back from, and a model "
            f"may have read one out of an earlier tool result before composing this request"
        )

    # TOOL_CHOSEN: exactly six keys, pinned.
    [chosen] = [e for e in entries if e.event_type is AuditEventType.TOOL_CHOSEN]
    assert set(chosen.payload) == {
        "run_id",
        "step_index",
        "attempt",
        "model",
        "named",
        "outcome",
    }, (
        "TOOL_CHOSEN's payload gained or lost a key. Its docstring argues the absence: 'no "
        "model output beyond the name' — this feature is the first thing to press on that "
        "rule and must not be the thing that erodes it"
    )
    assert chosen.payload["named"] == "provision"

    # PRE_DECISION: keys and hashes, never values.
    decisions = [e for e in entries if e.event_type is AuditEventType.PRE_DECISION]
    assert decisions, "the pipeline decided"
    for decision in decisions:
        # TOP LEVEL, not nested under "arguments" — `redact_arguments` returns
        # {argument_keys, argument_hashes} and the engine splats it into the payload. An
        # earlier version of this row read `payload["arguments"]`, found nothing, and
        # skipped its own assertion behind an `if` that was never true: a check that could
        # not fail, in the row whose whole job is proving an absence. The dispatched row
        # caught it, which is the argument for having one.
        assert "argument_keys" in decision.payload, (
            "PRE_DECISION no longer carries redacted argument keys — either the redaction "
            "stopped running or the payload shape moved, and this row would silently stop "
            "checking either way"
        )
        assert set(decision.payload["argument_keys"]) == set(THE_REQUEST), (
            "the redacted keys do not describe the request the model actually made"
        )
        assert "argument_hashes" in decision.payload, "hashes, never raw values"

    # AND THE ONE PLACE IT DOES REST.
    assert run.durability is not None
    stored = run.durability.closed_intents("run-040") + run.durability.open_intents("run-040")
    assert [i.arguments for i in stored] == [THE_REQUEST], (
        "the intent is the single durable home: resume re-invokes, and a hash cannot be "
        "re-invoked with"
    )


def test_row_m10_removing_a_finished_acts_request_breaks_nothing() -> None:
    """M10, FR-007a, SC-005a — and the one unsafe removal, named in the same row.

    A future retention control will clear these. This row is the constraint it inherits:
    clearing a **closed** bracket's request changes nothing, because resume reads arguments
    only for pending steps. Clearing an **open** one would make that revival re-invoke with
    nothing — this feature's own defect, reintroduced by policy. Finished acts only.
    """
    run, _, _ = _run(tools={"provision": {"repeatable": False}}, durable=True)
    _resolve(run, _Answers(Answer("provision", THE_REQUEST)))
    assert run.durability is not None
    provider = run.durability

    [closed] = provider.closed_intents("run-040")
    assert closed.arguments == THE_REQUEST

    # Clear it, exactly as a retention pass would. Reaching into the in-memory store's own
    # dict rather than through the protocol, because the protocol has no 'forget this'
    # operation yet — that is the retention control this row exists to constrain, and
    # writing the row against a method that does not exist would be writing the feature.
    assert isinstance(provider, InMemoryDurabilityProvider)
    provider._intents[("run-040", closed.idempotency_key)] = closed.model_copy(  # noqa: SLF001
        update={"arguments": None}
    )

    # Everything resume relies on is intact: the bracket is still closed, the key unchanged,
    # and the step still resolves as recorded.
    assert provider.open_intents("run-040") == [], "the bracket is still closed"
    [after] = provider.closed_intents("run-040")
    assert after.idempotency_key == closed.idempotency_key
    assert after.tool_name == closed.tool_name
    assert after.step_index == closed.step_index

    # THE UNSAFE REMOVAL, stated as an assertion rather than a comment: an OPEN bracket's
    # request is what its revival replays, so clearing it leaves nothing to replay.
    open_run, _, _ = _run(tools={"boom": {"repeatable": False}}, durable=True)
    open_run.registry.resolve("boom")  # registered
    assert open_run.durability is not None
    provider2 = open_run.durability
    from core.durability.types import IntentRecord

    provider2.record_intent(
        IntentRecord(
            run_id="run-040",
            step_index=0,
            tool_name="boom",
            idempotency_key="run-040:0:boom",
            arguments=THE_REQUEST,
            recorded_at=open_run.clock.now(),
        )
    )
    [pending] = provider2.open_intents("run-040")
    assert pending.arguments == THE_REQUEST, (
        "a PENDING intent's request is what its revival re-invokes with — a retention control "
        "that cleared this one would recreate the defect 040 exists to fix"
    )


def test_row_m11_nothing_expires_what_is_kept() -> None:
    """M11, FR-007b — the behaviour of "kept until removed", never the prose.

    The statement lives in the schema comment and the field docstring. This row asserts what
    the platform *does*: no elapsed time and no platform action removes a request. Six checks
    in this repository have matched a comment instead of code; this is not the seventh.
    """
    run, _, _ = _run(tools={"provision": {"repeatable": False}}, durable=True)
    _resolve(run, _Answers(Answer("provision", THE_REQUEST)))
    assert run.durability is not None
    provider = run.durability

    # Time passes — a lot of it — and the platform is asked to do its ordinary work.
    assert isinstance(run.clock, FrozenClock)
    run.clock.advance(timedelta(days=365))
    provider.open_intents("run-040")
    provider.closed_intents("run-040")

    [still_there] = provider.closed_intents("run-040")
    assert still_there.arguments == THE_REQUEST, (
        "the platform expired a kept request on its own. It must not: retention here is "
        "'until something removes it', and an unstated or self-enforcing retention is one "
        "nobody can hold the platform to"
    )


# --------------------------------------------------------------------- getting it wrong


def test_row_m4_a_malformed_answer_is_reasked_never_acted_on() -> None:
    """M4, FR-008, SC-006 — both halves.

    A bound that is never reached is not demonstrated by the path that does not reach it, so
    this row asserts the re-ask *and* the exhaustion.
    """
    run, handlers, sink = _run()
    chooser = _Answers(
        MalformedAnswer("entry carries no string 'tool'"),
        Answer("provision", {"path": "recovered"}),
    )
    resolution = _resolve(run, chooser)

    assert chooser.asked == 2, "the malformed answer was re-asked, not acted on"
    assert resolution.executed
    assert handlers["provision"].calls == [{"path": "recovered"}]

    malformed = [
        e
        for e in sink.all_entries()
        if e.event_type is AuditEventType.TOOL_CHOSEN
        and e.payload["outcome"] == str(ChoiceOutcome.MALFORMED)
    ]
    assert malformed, "the malformed attempt is recorded, not silently retried"
    assert malformed[0].payload["named"] == "", (
        "a malformed answer names no tool, and the trail carries no model output beyond a "
        "name — so there is nothing to record here"
    )


def test_row_m4a_exhausting_the_bound_ends_the_run() -> None:
    """**Prove M4's bound is a bound**: answer malformed past it, and the run must stop."""
    run, handlers, _ = _run()
    chooser = _Answers(*[MalformedAnswer("still unusable")] * (DEFAULT_RECHOICE_BOUND + 2))
    resolution = _resolve(run, chooser)

    assert resolution.outcome is ChoiceOutcome.EXHAUSTED
    assert resolution.is_terminal(), "the run stops rather than acting on the last answer"
    assert chooser.asked == DEFAULT_RECHOICE_BOUND, "and it stopped asking at the bound"
    assert handlers["provision"].calls == [], "nothing was performed"


def test_row_m5_an_oversized_request_is_refused_with_its_size_never_its_content() -> None:
    """M5, FR-007c, FR-007d, SC-006a — refused and re-asked, never truncated.

    Truncation is the fail-open shape: it performs a *different* act from the one described,
    which is worse than performing none. And the refusal records the byte count, on the
    precedent of a message the platform declined to accept — recorded by its size.
    """
    run, handlers, sink = _run()
    oversized = {"path": SENTINEL + "x" * DEFAULT_REQUEST_BYTES}
    chooser = _Answers(Answer("provision", oversized), Answer("provision", {"path": "small"}))
    resolution = _resolve(run, chooser)

    assert handlers["provision"].calls == [{"path": "small"}], (
        "the oversized request was refused and re-asked — and NOT truncated, which would "
        "have performed an act nobody described"
    )
    assert resolution.executed

    for entry in sink.all_entries():
        rendered = json.dumps(entry.payload, default=str)
        assert SENTINEL not in rendered, (
            "the oversized refusal recorded the request's CONTENT. It records the size and "
            "the bound; recording the content would let an append-only trail grow at "
            "whatever rate a request can be refused"
        )


def test_row_m6_a_raised_bound_is_honoured_the_default_holds_elsewhere() -> None:
    """M6, SC-006b — the same request to both, which is the row.

    Two different requests would prove nothing about the bound. One request, two capabilities,
    two outcomes: the one that raised its own limit accepts what the default refuses.
    """
    # Comfortably over the default and comfortably under the raised one, so the row turns
    # on the BOUND rather than on where a serialisation boundary happens to fall.
    request = {"blob": "y" * (DEFAULT_REQUEST_BYTES * 2)}

    modest_run, modest_handlers, _ = _run(tools={"modest": {}})
    modest = _resolve(modest_run, _Answers(Answer("modest", request), Answer("modest", {})))
    assert modest_handlers["modest"].calls == [{}], "the default bound refused it"

    generous_run, generous_handlers, _ = _run(
        tools={"generous": {"max_request_bytes": 4 * 1024 * 1024}}
    )
    generous = _resolve(generous_run, _Answers(Answer("generous", request)))
    assert generous.executed
    assert generous_handlers["generous"].calls == [request], (
        "a capability that raised its own bound must accept what the default refuses — "
        "otherwise the per-capability limit is decoration"
    )
    assert modest.executed, "and the modest one still completed, on its second answer"


def test_row_m17_malformed_refused_and_failed_are_three_records() -> None:
    """M17, FR-009 — an operator told the wrong one fixes the wrong thing.

    Three situations, three responses, three records:

    * **malformed** — a *choice* failure. Re-asked within the bound, never invoked, and
      recorded as a `TOOL_CHOSEN` outcome naming nothing.
    * **refused** — the *pipeline's* decision. Recorded as a `PRE_DECISION` deny, and the act
      never happens.
    * **failed** — permitted, performed, and the capability itself said no. Recorded as an
      executed `TOOL_OUTCOME` carrying `success=False`.

    The middle one is not a platform failure and the last one is not a governance refusal.
    Collapsing any pair would send whoever is debugging it somewhere else entirely.
    """

    def rejecting(arguments: Any) -> Any:
        raise ValueError("this capability rejects this request")

    registry = ToolRegistry()
    registry.register("rejects", rejecting)
    registry.register("permitted", _Watching())
    registry.register("forbidden", _Watching())
    clock = frozen_clock()
    sink = capture_audit()
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-m17",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"rejects", "permitted"})),
        identity_fabric=fake_identity_fabric(
            tool_names={"rejects", "permitted", "forbidden"},
            ceiling_tools={"rejects", "permitted"},
        ),
        clock=clock,
        registry=registry,
        audit_sink=sink,
    )
    run.clock = clock
    permitted = ["permitted", "rejects", "forbidden"]

    # 1. MALFORMED — re-asked, then a good answer lands.
    resolve_step_tool(
        run,
        task="t",
        permitted=permitted,
        step_index=0,
        model="fixture/scripted@1",
        chooser=_Answers(MalformedAnswer("not an object"), Answer("permitted", {})),
    )

    # 2. REFUSED — a real tool outside this run's ceiling. Governance decides.
    refused = resolve_step_tool(
        run,
        task="t",
        permitted=permitted,
        step_index=1,
        model="fixture/scripted@1",
        chooser=_Answers(*[Answer("forbidden", {})] * DEFAULT_RECHOICE_BOUND),
    )

    # 3. FAILED ON ITS OWN TERMS — permitted, performed, rejected by the capability.
    failed = resolve_step_tool(
        run,
        task="t",
        permitted=permitted,
        step_index=2,
        model="fixture/scripted@1",
        chooser=_Answers(*[Answer("rejects", {"bad": True})] * DEFAULT_RECHOICE_BOUND),
    )

    entries = sink.all_entries()

    # (1) The malformed answer is its own outcome, naming nothing.
    malformed = [
        e
        for e in entries
        if e.event_type is AuditEventType.TOOL_CHOSEN
        and e.payload["outcome"] == str(ChoiceOutcome.MALFORMED)
        and e.payload["named"] == ""
    ]
    assert malformed, "a malformed answer is recorded as a choice outcome naming no tool"

    # (2) The governance refusal is a PRE_DECISION deny, and nothing executed.
    denials = [
        e
        for e in entries
        if e.event_type is AuditEventType.PRE_DECISION and e.payload.get("outcome") == "deny"
    ]
    assert denials, "a tool outside the ceiling is denied by the pipeline"
    assert not refused.executed

    # (3) The capability's own rejection: governance PERMITTED it, and then it failed.
    failures = [
        e
        for e in entries
        if e.event_type is AuditEventType.TOOL_OUTCOME and not e.payload["success"]
    ]
    assert failures, "an executed-and-failed act is an outcome, not a denial"
    assert failures[0].payload["error_code"] == "ValueError", (
        "the failure carries the error's TYPE and not its message — a capability's words "
        "about a request are still words about model-supplied content"
    )
    assert not failed.executed

    # AND THE THREE ARE DISTINGUISHABLE, which is the requirement rather than their existence.
    assert malformed[0].event_type is not denials[0].event_type is not failures[0].event_type, (
        "three situations must not read alike"
    )


# ------------------------------------------------------------ nothing that worked moves


def test_row_m13_every_existing_recording_means_what_it_meant() -> None:
    """M13, FR-010, SC-007 — the compatibility claim, derived rather than memorised.

    Two halves. First: `"plan,apply,-"` parses to exactly the three choices it always did —
    a bare name is a choice with no arguments. Second: the **behaviour** consumers of the
    recording helpers are untouched, and the inventory is derived by scanning the tree rather
    than by a list somebody has to remember to update. Enumerations of this tree have
    undercounted twice.
    """
    from pathlib import Path

    from core.choice.recorded import parse_recording

    parsed = parse_recording("plan,apply,-")
    assert parsed == ["plan", "apply", "-"], (
        "a bare-name recording must parse exactly as it always has — this is what FR-010 "
        "protects, and it is what four merged suites are driven by"
    )

    root = Path(__file__).resolve().parents[3]
    consumers = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "tests").rglob("*.py")
        if any(
            token in path.read_text() for token in ("recording(", "scripted_chooser", "choice_args")
        )
    )
    # Excluding this file: it is 040's OWN row file and asserts the widened protocol by
    # design. What the invariant protects is the suites that predate the widening.
    this_file = __file__[len(str(root)) + 1 :]
    asserts_protocol = [
        name for name in consumers if name != this_file and ".choose(" in (root / name).read_text()
    ]
    assert asserts_protocol == ["tests/conformance/choice/test_the_double_is_faithful.py"], (
        f"the set of suites asserting the Chooser PROTOCOL changed: {asserts_protocol}. "
        f"Exactly one may — the protocol's return type is what 040 declares it widens — and "
        f"every other recording consumer asserts BEHAVIOUR and must stay byte-identical"
    )
    assert len(consumers) >= 8, (
        f"only {len(consumers)} recording consumers found; the inventory has undercounted "
        f"twice already and a shrinking scan is how it happens a third time"
    )


def test_row_m14_a_recording_can_carry_a_structured_choice() -> None:
    """M14, FR-001 — the `[`-prefixed grammar, and one sentinel for both.

    Includes a round trip through an environment variable, because that is how a recording
    actually travels — JSON survives shells less obviously than bare words do.
    """
    import os

    from core.choice.recorded import RecordedChooser, parse_recording

    wire = json.dumps(
        [
            {"tool": "vault_write", "arguments": {"path": "a/b", "cas": 0}},
            {"tool": "-"},
        ]
    )
    os.environ["RUN_CHOICE_RECORDING_TEST"] = wire
    try:
        round_tripped = os.environ["RUN_CHOICE_RECORDING_TEST"]
    finally:
        del os.environ["RUN_CHOICE_RECORDING_TEST"]
    assert round_tripped == wire, "the structured form survives an environment variable"

    chooser = RecordedChooser(parse_recording(round_tripped))
    request = ChoiceRequest(task="t", permitted=("vault_write",), step_index=0, attempt=0)
    first = chooser.choose(request)
    assert first == Answer("vault_write", {"path": "a/b", "cas": 0})
    assert chooser.choose(request).name == "", (
        "the '-' sentinel means the same thing in both grammars — one rule, and 'the run "
        "ended' is never inferred from punctuation"
    )


def test_row_m15_the_same_capability_twice_two_requests_two_acts() -> None:
    """M15 — two intents, and the second is not mistaken for a repeat of the first.

    This is R2's claim measured rather than remembered: 040 has no programs, so each act is
    its own step and the keys differ by construction. The row is what keeps that true by
    observation instead of by argument.
    """
    run, handlers, _ = _run(tools={"provision": {"repeatable": False}}, durable=True)

    for step, target in enumerate(["first", "second"]):
        run.step_index = step
        resolve_step_tool(
            run,
            task="t",
            permitted=["provision"],
            step_index=step,
            model="fixture/scripted@1",
            chooser=_Answers(Answer("provision", {"path": target})),
        )

    assert handlers["provision"].calls == [{"path": "first"}, {"path": "second"}]
    assert run.durability is not None
    intents = run.durability.closed_intents("run-040") + run.durability.open_intents("run-040")
    assert len(intents) == 2, "two acts, two intents"
    assert len({i.idempotency_key for i in intents}) == 2, (
        "the two keys differ by construction — each act is its own step"
    )
    assert sorted((i.arguments or {})["path"] for i in intents) == ["first", "second"]


@pytest.mark.parametrize("bound", [DEFAULT_REQUEST_BYTES])
def test_the_default_bound_is_stated_not_emergent(bound: int) -> None:
    """FR-007 — the bound is a named constant a reader can find, not a magic number."""
    assert bound == 64 * 1024
    registry = ToolRegistry()
    registry.register("plain", _Watching())
    assert registry.resolve("plain").max_request_bytes == DEFAULT_REQUEST_BYTES


# ---------------------------------------------------------------- the production caller


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_row_m18_a_dispatched_run_acts_on_what_the_model_named() -> None:
    """M18, SC-001 — in the environment where dispatched work actually happens.

    **Every other row in this file could pass while this one was false.** That is not a
    hypothetical: it is the state 036 and 038 both shipped in, with green rows over
    capabilities no allocation could reach. `verify-the-production-caller` and
    `run-the-served-process` are the same lesson from two directions, and this is where they
    are settled for 040.

    **The recording travels as JSON through Nomad meta interpolation** — HCL quoting included,
    which is part of what this row proves rather than a nuisance to work around. A structured
    recording that survives a unit test and dies in an environment variable would leave the
    dispatched path exactly as unproven as it was before.
    """
    from tests.conformance.choice import harness as c
    from tests.conformance.durability import dispatch_harness as h

    connection = h.connection()
    try:
        # DISTINCT PER INVOCATION, not merely per row. A fixed id accumulates every
        # earlier attempt under one correlation, and the assertions below then read
        # events this run did not produce — which is how the first version of this row
        # reported empty argument keys while the run it dispatched carried them.
        # `dispatch_harness` states the rule; this row learned it the other way.
        run_id = h.unique("m18-model-supplied-arguments")
        # The structured grammar, carrying a path the platform would never have chosen: the
        # pre-040 constant wrote to `conformance/probe`, so an act against THIS path cannot
        # have come from anywhere but the recording.
        target = "conformance/m18-model-said-so"
        wire = json.dumps(
            [
                {"tool": "vault_write", "arguments": {"path": target, "cas": 0}},
                {"tool": "-"},
            ]
        )
        alloc = c.run_to_completion(run_id, answers=["vault_write", "-"], choice_recording=wire)

        assert c.named(connection, run_id)[:1] == ["vault_write"], (
            f"the dispatched run did not choose from the structured recording; "
            f"`nomad alloc logs {alloc}`"
        )

        outcomes = h.events(connection, run_id, "tool_outcome")
        assert outcomes, f"no tool ran in the allocation; `nomad alloc logs {alloc}`"
        assert all(o.get("success") for o in outcomes), (
            f"the model-directed act failed in the allocation: {outcomes}; "
            f"`nomad alloc logs {alloc}`"
        )

        # THE ASSERTION THIS ROW EXISTS FOR: the act reached the product against the target
        # the MODEL named. The trail carries hashes rather than values, so the observable is
        # the argument key set the pipeline redacted — a platform-supplied constant and a
        # model-supplied request are different requests, and this is where that becomes a
        # fact about production rather than about a unit test.
        decisions = h.events(connection, run_id, "pre_decision")
        keys = [tuple(sorted(d.get("argument_keys") or ())) for d in decisions]
        assert ("cas", "path") in keys, (
            f"no invoke carried the model's argument keys; got {keys}; `nomad alloc logs {alloc}`"
        )
    finally:
        connection.close()
