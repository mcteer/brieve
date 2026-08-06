# SPDX-License-Identifier: Apache-2.0
"""A chooser that replays a recording instead of calling a provider.

**Why this is production code and not a test fake.** FR-011 says model calls in the merge lane
must not depend on a live provider — a gate that cannot run without a vendor is a gate that
stops running — and the merge lane includes rows that drive a *dispatched* run inside an
allocation. An allocation cannot be handed a Python object, so the stand-in has to be
something a run can resolve for itself.

The matrix already contemplates this: `QualifiedBy` is ``fixture`` or ``live``, where fixture
means a cell qualified against a **recording**. A cell whose model identifier names the
``fixture`` provider is served here.

**Two keys, not one.** Reaching this chooser requires a `fixture/...` cell that the matrix
qualifies *and* a definition that binds it for the role. An operator cannot arrive here by
forgetting something; they have to author two records that say so. That is what keeps FR-002's
guarantee — no arithmetic selection reachable from a production run — from being traded for a
scripted selection reachable by accident.

**It is not a mock of the loop** (research F5). Everything between "the run needs a choice" and
"a choice came back" is the same code either way: the binding is read, the matrix validates the
cell, an identifier is resolved, a chooser is built for it, the bound applies, and every answer
goes to `invoke_tool`. Only the last hop differs.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core.choice.chooser import Answer, ChoiceRequest, ChooserUnavailable, MalformedAnswer

#: What a recording writes to mean "the model names nothing here" — the terminal answer that
#: ends a run. Spelled, because an empty element in a comma-separated list is indistinguishable
#: from a trailing separator, and "the run ended" is not something to infer from punctuation.
NOTHING = "-"


@dataclass(frozen=True)
class MalformedEntry:
    """A recording entry that does not parse as a name and its arguments (040, M4's fixture).

    Kept as a marker rather than raised at parse time, because a recording is consumed one
    answer per *ask*: the malformed entry must surface at the step that consumes it, exactly
    as a model producing an unusable object would, so the re-choice bound sees it.
    ``shape`` describes what was wrong; it never carries the entry's content.
    """

    shape: str


class RecordedChooser:
    """Replays a fixed sequence of answers, one per *ask* — or names the first permitted tool.

    Per ask rather than per step, and the difference is the whole reason a recording can
    exercise the re-choice loop at all: a recording of ``["apply", "plan"]`` at a step whose
    ceiling forbids `apply` produces a refusal, a second ask, and a permitted choice — which is
    FR-004a and FR-004c happening for real rather than being simulated.

    **An ABSENT recording is a defined behaviour, not a misconfiguration**, and the first
    enclave run of this feature is what settled that. Every pre-020 dispatched row that invokes
    tools now consults a model, and requiring each to carry a script would have meant carrying
    that script through the suspended-run index and the sweeper's resume dispatch — a column in
    a control-plane table, for a test affordance. So a fixture model with nothing recorded
    answers with the first tool the request permits.

    **That is a model's behaviour, not the loop's**, and the distinction is the whole of
    SC-002. It sits on the far side of the seam, reached only through a cell the matrix
    qualified and a definition bound; the loop still asks, still records what came back, and
    still puts it to `invoke_tool`. What FR-002 forbids is the *loop* computing an index, and
    the loop no longer can.

    A recording that is present and runs out is still an error — see :meth:`choose`. Supplying
    a script and having it end early is a row that does not cover the run it was written for,
    which is a different thing from not supplying one.
    """

    def __init__(
        self,
        answers: Sequence[str | Answer | MalformedEntry],
        *,
        bare_name_arguments: Mapping[str, Any] | None = None,
    ) -> None:
        #: Entries stay in their authored form and are normalised per ask.
        self._answers = list(answers)
        self._asked = 0
        #: WHAT A BARE NAME HAS ALWAYS MEANT (040, FR-010), supplied by the caller.
        #:
        #: Before 040 a recording named a tool and the *platform* supplied every tool's
        #: arguments from a fixture constant — so `"vault_write"` meant "write to the probe
        #: path", not "write with nothing". Reading a bare name as an empty request would
        #: change what every existing recording means, and `vault_write` raises without
        #: `cas`: the dispatched suites would fail, which is exactly how this was found.
        #:
        #: Passed in rather than known here, because which arguments a fixture implies is
        #: the fixture's business and this module is core. Absent, a bare name is genuinely
        #: an empty request — which is the right answer for any caller that never had a
        #: platform constant behind it.
        self._bare_name_arguments = dict(bare_name_arguments or {})

    @property
    def asked(self) -> int:
        """How many times this chooser has been consulted.

        The observable SC-005 rests on. A resumed run must re-issue no provider call for a
        step it already executed, and with a recording standing in for the provider, "no
        provider call" is exactly "this counter did not move".
        """
        return self._asked

    def choose(self, request: ChoiceRequest) -> Answer:
        self._asked += 1
        if not self._answers:
            # Nothing recorded: name the first tool this request permits, with no arguments
            # — the true answer for the fixture tools (040). Sorted, so the answer is stable
            # across runs — a fixture model that answered differently on identical input
            # would make every row built on it intermittent.
            first = sorted(request.permitted)[0] if request.permitted else ""
            return Answer(first, dict(self._bare_name_arguments) if first else {})

        if self._asked > len(self._answers):
            # Running off the end is a recording that does not cover the run it was written
            # for. Raised rather than answered with "" — an empty answer is the *terminal*
            # outcome, so defaulting to it would end runs quietly whenever a recording was
            # short, and a row asserting a terminal run would pass for the wrong reason.
            raise ChooserUnavailable(
                f"the recording holds {len(self._answers)} answers and a "
                f"{self._asked}th was asked for at step {request.step_index}",
                reason_code="recording_exhausted",
            )
        answer = self._answers[self._asked - 1]
        if isinstance(answer, MalformedEntry):
            # Surfaced at the step that consumes it, exactly as a model producing an
            # unusable object would be — so the re-choice bound sees it (040, FR-008).
            raise MalformedAnswer(answer.shape)
        if isinstance(answer, Answer):
            # A STRUCTURED entry says what it wants, including when it wants nothing. Its
            # arguments are never topped up from the bare-name default — that default exists
            # to preserve what an OLD recording meant, and a structured entry is new.
            return Answer("", {}) if answer.name == NOTHING else answer
        if answer == NOTHING:
            return Answer("")
        return Answer(answer, dict(self._bare_name_arguments))


def parse_recording(raw: str) -> list[str | Answer | MalformedEntry]:
    """Two grammars, chosen by the first non-space character (040, research R14).

    A recording starting with ``[`` is a JSON list of ``{"tool": ..., "arguments": {...}}``;
    anything else splits on commas exactly as it always has, and **a bare name is a choice
    with no arguments** — ``"plan,apply,-"`` yields exactly what it yielded before the
    widening. Two grammars rather than one widened one, because the value travels as an
    environment variable parsed by a comma split, JSON contains commas, and the comma form
    is load-bearing for every recording-driven suite in the merge lane (FR-010).

    The ``"-"`` terminal sentinel serves both forms — one rule, and *"the run ended"* is
    never inferred from punctuation. A JSON entry that is not an object with a string
    ``"tool"`` and a mapping ``"arguments"`` becomes a :class:`MalformedEntry`, surfaced at
    the ask that consumes it; a recording that is ``[``-prefixed and not JSON at all is a
    configuration error and raises here, because nothing about it is per-entry.

    Empty in, empty out.
    """
    stripped = raw.lstrip()
    if not stripped.startswith("["):
        return [part.strip() for part in raw.split(",") if part.strip()]

    try:
        entries = json.loads(stripped)
    except ValueError as exc:
        raise ValueError(
            "recording starts with '[' but is not valid JSON — the structured grammar is "
            "all-or-nothing, and a recording nobody can parse is a configuration error, not "
            "a model behaviour"
        ) from exc
    if not isinstance(entries, list):
        raise ValueError("a structured recording must be a JSON list of choices")

    parsed: list[str | Answer | MalformedEntry] = []
    for entry in entries:
        if not isinstance(entry, dict):
            parsed.append(MalformedEntry(shape=f"entry is {type(entry).__name__}, not an object"))
            continue
        tool = entry.get("tool")
        arguments = entry.get("arguments", {})
        if not isinstance(tool, str) or not tool.strip():
            parsed.append(MalformedEntry(shape="entry carries no string 'tool'"))
            continue
        if not isinstance(arguments, dict):
            parsed.append(
                MalformedEntry(shape=f"'arguments' is {type(arguments).__name__}, not an object")
            )
            continue
        parsed.append(Answer("" if tool.strip() == NOTHING else tool.strip(), arguments))
    return parsed


__all__ = ["NOTHING", "MalformedEntry", "RecordedChooser", "parse_recording"]
