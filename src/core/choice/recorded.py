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

from collections.abc import Sequence

from core.choice.chooser import ChoiceRequest, ChooserUnavailable

#: What a recording writes to mean "the model names nothing here" — the terminal answer that
#: ends a run. Spelled, because an empty element in a comma-separated list is indistinguishable
#: from a trailing separator, and "the run ended" is not something to infer from punctuation.
NOTHING = "-"


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

    def __init__(self, answers: Sequence[str]) -> None:
        self._answers = list(answers)
        self._asked = 0

    @property
    def asked(self) -> int:
        """How many times this chooser has been consulted.

        The observable SC-005 rests on. A resumed run must re-issue no provider call for a
        step it already executed, and with a recording standing in for the provider, "no
        provider call" is exactly "this counter did not move".
        """
        return self._asked

    def choose(self, request: ChoiceRequest) -> str:
        self._asked += 1
        if not self._answers:
            # Nothing recorded: name the first tool this request permits. Sorted, so the
            # answer is stable across runs — a fixture model that answered differently on
            # identical input would make every row built on it intermittent.
            return sorted(request.permitted)[0] if request.permitted else ""

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
        return "" if answer == NOTHING else answer


def parse_recording(raw: str) -> list[str]:
    """``"plan,apply,-"`` → ``["plan", "apply", "-"]``. Empty in, empty out."""
    return [part.strip() for part in raw.split(",") if part.strip()]


__all__ = ["NOTHING", "RecordedChooser", "parse_recording"]
