# SPDX-License-Identifier: Apache-2.0
"""The re-choice budget: a denial teaches the model, and the bound keeps that honest.

Clarification made governance a **signal** rather than only a wall — a refused choice goes
back to the model, which may choose again. That is the sharper answer and it created the
sharper risk, stated plainly in the spec: an agent that keeps asking must not be able to grind
past its ceiling until something gives. Without a bound, governance-as-a-signal is
governance-as-a-suggestion.

So: attempts are bounded, **every** refusal is recorded rather than only the last before a
success, and exhausting the bound is itself a recorded terminal outcome.

**The bound is per step, not per run.** A run that legitimately needs several tools must not
inherit a smaller budget because an earlier step took two attempts — that would make a run's
remaining freedom depend on its own history in a way nothing in the definition describes.

**Where this sits relative to the bracket** (research F3). `invoke_tool` brackets every
non-repeatable tool itself, keyed ``{run_id}:{step_index}:{tool}``. A second choice at the same
step names a *different* tool, so it yields a different key and cannot collide. A bound
implemented as a retry *around* the bracket would make that key ambiguous on resume — two
attempts, one key — and re-observe-never-re-execute would have to guess which. That is the
durability guarantee breaking quietly, which is why this loop calls `invoke_tool` once per
attempt rather than wrapping it in a retry.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from core.choice.chooser import (
    Answer,
    Choice,
    ChoiceOutcome,
    ChoiceRequest,
    Chooser,
    MalformedAnswer,
    is_tool_name,
    record_choice,
)
from core.run import RunState
from core.tools.invoke import InvokeResult, invoke_tool

#: How many times a model may name a tool at one step before the run stops.
#:
#: Three: the first choice, and two chances to learn from a refusal. Small on purpose — an
#: agent grinding against its ceiling and an agent thinking hard look identical from outside,
#: and a generous bound makes the two indistinguishable for longer.
#:
#: Not per-definition today, and saying so is more honest than implying a record that does not
#: exist: no control-plane field carries a re-choice budget. When one exists it is read here.
DEFAULT_RECHOICE_BOUND: Final[int] = 3


@dataclass(frozen=True)
class StepResolution:
    """How one step's tool was decided, and what happened to it.

    Returned rather than acted on, for the reason `ResumeDecision` gives one module over:
    the reasoning belongs where a caller and the audit trail can both see it, not buried in
    control flow.
    """

    outcome: ChoiceOutcome
    #: The tool that ran, or "" when none did.
    tool: str = ""
    #: The governed pipeline's own answer, when a tool was invoked at all.
    result: InvokeResult | None = None
    #: How many times the model was asked at this step.
    attempts: int = 0
    #: The run entered SUSPENDED while this step was being resolved. **Not a refusal** — a
    #: wait — and the caller must file it as one rather than failing the allocation.
    suspended: bool = False
    #: Every choice made at this step, in order. The caller needs the count; the trail
    #: already holds the contents.
    choices: tuple[Choice, ...] = ()

    def is_terminal(self) -> bool:
        """True when the run must stop rather than continue to the next step."""
        return self.outcome in {
            ChoiceOutcome.EMPTY,
            ChoiceOutcome.EXHAUSTED,
        }

    @property
    def executed(self) -> bool:
        """A tool was named AND the governed pipeline allowed it.

        Two conditions, because `NAMED` says only that a real tool went to `invoke_tool` —
        the verdict is the pipeline's and lives on ``result``. Collapsing them would put the
        permission decision back in the choosing code by the back door.
        """
        return bool(self.tool) and self.result is not None and self.result.allowed


def _record(
    run: Any, step_index: int, attempt: int, model: str, named: str, outcome: ChoiceOutcome
) -> Choice:
    """Write the trail entry and return the in-memory twin, in that order.

    The order is deliberate: the entry is the record, and the returned `Choice` is a
    convenience for the caller. If the append raises, nothing is appended to ``choices``
    either — so the two never disagree about what happened.
    """
    record_choice(
        run,
        step_index=step_index,
        attempt=attempt,
        model=model,
        named=named,
        outcome=outcome,
    )
    return Choice(step_index=step_index, attempt=attempt, named=named, outcome=outcome, model=model)


def resolve_step_tool(
    run: Any,
    *,
    task: str,
    permitted: Sequence[str],
    step_index: int,
    model: str,
    chooser: Chooser,
    bound: int = DEFAULT_RECHOICE_BOUND,
    already_chosen: Answer | None = None,
) -> StepResolution:
    """Ask a model what to do at this step, and carry the answer into the governed entry.

    **The model's arguments travel to the invoke** (040, FR-001). Until 040 this function
    took an ``arguments`` mapping from its caller — a fixture constant, supplied by the
    platform for every tool a model named — and the model could choose the verb but never
    the object. The answer now carries both, and the platform still performs the act:
    nothing about a governed step moves (research R1).

    ``already_chosen`` is the resume path (FR-008). When a disrupted run left an open intent
    at this step, that intent names the tool the model *already* chose — **and, since 040,
    the arguments it chose it with** (FR-004) — and honouring both is what makes
    re-observation honest: re-asking would let a resumed run execute a different act from
    the one whose bracket is open, which is re-execution wearing observation's clothes. It
    costs no provider call, which is the observable half SC-005 asserts. The recorded answer
    is honoured whole: it already passed every check when it was first made, and refusing it
    now would strand a bracket that only re-invoking can resolve.

    **Nothing here decides permission.** Each named tool goes to `invoke_tool` — the same
    call a scripted name went to, unchanged — and what comes back is the core's answer. That
    is what makes FR-003's "no new path to a capability" structural rather than a promise.

    A `ChooserUnavailable` propagates. FR-007: a provider failure ends the run in a recorded
    terminal state and never falls back to a non-model selection.
    """
    known = run.registry.tool_names()
    refused: list[tuple[str, str]] = []
    choices: list[Choice] = []

    for attempt in range(max(bound, 1)):
        # Whether THIS iteration is replaying a recorded act rather than asking. Tracked
        # rather than re-derived below: the size bound is skipped only for a replay, and a
        # second expression testing "roughly the same thing" is how the two drift apart.
        replayed = attempt == 0 and already_chosen is not None and bool(already_chosen.name)
        if replayed:
            assert already_chosen is not None  # narrowed by `replayed`
            answer = already_chosen
        else:
            try:
                answer = chooser.choose(
                    ChoiceRequest(
                        task=task,
                        permitted=tuple(permitted),
                        step_index=step_index,
                        attempt=attempt,
                        refused=tuple(refused),
                    )
                )
            except MalformedAnswer as exc:
                # The answer does not parse as a name and its arguments (040, FR-008).
                # Re-asked within the same bound as every other unusable answer, never
                # acted on, and never repaired by dropping the malformed parts — guessing
                # at a malformed request is how a platform performs an act nobody asked
                # for. ``named`` is empty in the record: the trail carries no model output
                # beyond a tool name, and a malformed answer has none.
                choices.append(
                    _record(run, step_index, attempt, model, "", ChoiceOutcome.MALFORMED)
                )
                refused.append(("", f"malformed_answer: {exc}"))
                continue
        named = answer.name.strip()

        if not named:
            # The model named nothing. Terminal, and emphatically not defaulted to a tool —
            # defaulting here would be `_tool_for_step` returning through the back door.
            choices.append(_record(run, step_index, attempt, model, named, ChoiceOutcome.EMPTY))
            return StepResolution(
                outcome=ChoiceOutcome.EMPTY, attempts=attempt + 1, choices=tuple(choices)
            )

        if not is_tool_name(named, known):
            # Not a tool at all — the model misunderstood its task. Distinct from a real tool
            # it may not have, which is a model that understood and reached past its ceiling.
            # Re-choosable within the bound, because a malformed answer is exactly the kind of
            # thing being told about tends to fix.
            choices.append(_record(run, step_index, attempt, model, named, ChoiceOutcome.MALFORMED))
            refused.append((named, "not_a_tool"))
            continue

        # THE SIZE BOUND, centrally and before any invoke (040, FR-007). The named tool's
        # own registration says how large a request it accepts; over it, the answer is
        # refused and re-asked — NEVER truncated, because truncating performs a different
        # act from the one described, which is worse than performing none (FR-007c). The
        # refusal carries the byte count and the bound and none of the content (FR-007d,
        # on TURN_REFUSED's precedent: a message the platform declined to accept is
        # recorded by its size). Skipped for `already_chosen`: a recorded act passed this
        # check when it was made, and refusing it now would strand an open bracket.
        request_arguments = dict(answer.arguments)
        if not replayed:
            try:
                encoded = json.dumps(request_arguments, separators=(",", ":")).encode("utf-8")
            except (TypeError, ValueError) as exc:
                # A request that cannot even be serialised is malformed, not a crash. It
                # reaches here only from a chooser that fabricated a non-JSON value, and
                # the honest response is the one every other unusable answer gets: refused
                # and re-asked. Letting it propagate would end the run on a model mistake
                # the bound exists to absorb. The type travels; the value does not.
                choices.append(
                    _record(run, step_index, attempt, model, named, ChoiceOutcome.MALFORMED)
                )
                refused.append((named, f"unserialisable_request: {type(exc).__name__}"))
                continue
            size = len(encoded)
            limit = run.registry.resolve(named).max_request_bytes
            if size > limit:
                choices.append(
                    _record(run, step_index, attempt, model, named, ChoiceOutcome.MALFORMED)
                )
                refused.append((named, f"request_too_large size={size} bound={limit}"))
                continue

        # RECORDED BEFORE IT RUNS, and both halves of that matter.
        #
        # Ordering: every other causal record in this trail precedes its consequences, and the
        # first dispatched run of this feature wrote a tool's outcome BEFORE the choice that
        # caused it — an investigator reading in order saw an effect before its reason.
        #
        # Fail-closed: `record_choice` does not swallow, so a choice that cannot be recorded
        # never reaches `invoke_tool`. Recording afterwards would let a tool execute and the
        # append fail, leaving an effect with nothing saying who chose it. The hook engine
        # denies on exactly this condition for exactly this reason.
        choices.append(_record(run, step_index, attempt, model, named, ChoiceOutcome.NAMED))

        result = invoke_tool(run, named, request_arguments)

        if result.allowed:
            return StepResolution(
                outcome=ChoiceOutcome.NAMED,
                tool=named,
                result=result,
                attempts=attempt + 1,
                choices=tuple(choices),
            )

        # A SUSPENSION IS NOT A REFUSAL, and re-choosing past one would be worse than the
        # bug 014 fixed at the entrypoint: the dependency gate suspends a run whose product is
        # unreachable, so a second choice would either hit the same unreachable product or
        # reach a different one while the run is already waiting.
        if run.state is RunState.SUSPENDED:
            return StepResolution(
                outcome=ChoiceOutcome.NAMED,
                tool=named,
                result=result,
                attempts=attempt + 1,
                suspended=True,
                choices=tuple(choices),
            )

        # FR-004a: the denial becomes context, so the next ask carries it.
        #
        # FR-004c is satisfied by the entry written above rather than by one written here: a
        # run denied four times and permitted on the fifth leaves FIVE `tool_chosen` entries
        # at this step, each with the `PRE_DECISION` its invocation produced. A trail showing
        # only the success would describe the wrong run, and this one cannot — the record is
        # written before the pipeline is consulted, so it exists whatever the pipeline says.
        refused.append((named, result.reason_code))

    # FR-004b. The bound is what keeps governance-as-a-signal from becoming
    # governance-as-a-suggestion, and exhausting it is recorded rather than left to be
    # inferred from a run of refusals that simply stops.
    choices.append(_record(run, step_index, max(bound, 1), model, "", ChoiceOutcome.EXHAUSTED))
    return StepResolution(
        outcome=ChoiceOutcome.EXHAUSTED, attempts=max(bound, 1), choices=tuple(choices)
    )


def record_unconsulted_step(run: Any, *, step_index: int) -> None:
    """Say in the trail that this step asked no model (FR-002a, FR-002b).

    The `invoke_tools` carve-out is a production path that runs steps and invokes no tool, so
    it has nothing to choose and asking would be a provider call whose answer is discarded.
    That is defensible. What is not defensible is leaving it *invisible*: a run that looks
    governed, executed nothing, and consulted nobody must not be indistinguishable from one
    that consulted a model — and distinguishing them by the **absence** of `TOOL_CHOSEN`
    entries is the weak form of evidence `STEP_REOBSERVED` was added one feature ago to
    replace. An investigator should not have to notice that nothing is there.
    """
    record_choice(
        run,
        step_index=step_index,
        attempt=0,
        model="",
        named="",
        outcome=ChoiceOutcome.NOT_CONSULTED,
    )


__all__ = [
    "DEFAULT_RECHOICE_BOUND",
    "StepResolution",
    "record_unconsulted_step",
    "resolve_step_tool",
]
