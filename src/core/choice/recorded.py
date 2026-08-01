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
    """Replays a fixed sequence of answers, one per *ask*.

    Per ask rather than per step, and the difference is the whole reason a recording can
    exercise the re-choice loop at all: a recording of ``["apply", "plan"]`` at a step whose
    ceiling forbids `apply` produces a refusal, a second ask, and a permitted choice — which is
    FR-004a and FR-004c happening for real rather than being simulated.
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
        if self._asked >= len(self._answers):
            # Running off the end is a recording that does not cover the run it was written
            # for. Raised rather than answered with "" — an empty answer is the *terminal*
            # outcome, so defaulting to it would end runs quietly whenever a recording was
            # short, and a row asserting a terminal run would pass for the wrong reason.
            raise ChooserUnavailable(
                f"the recording holds {len(self._answers)} answers and a "
                f"{self._asked + 1}th was asked for at step {request.step_index}",
                reason_code="recording_exhausted",
            )
        answer = self._answers[self._asked]
        self._asked += 1
        return "" if answer == NOTHING else answer


def parse_recording(raw: str) -> list[str]:
    """``"plan,apply,-"`` → ``["plan", "apply", "-"]``. Empty in, empty out."""
    return [part.strip() for part in raw.split(",") if part.strip()]


__all__ = ["NOTHING", "RecordedChooser", "parse_recording"]
