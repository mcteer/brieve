# SPDX-License-Identifier: Apache-2.0
"""A relevance judge for the hermetic lanes (043, T004).

DECLARED_FAKE_RELEVANCE_JUDGE = (
    "Stands in for a model asked whether claims answer a question. It AFFIRMS EVERYTHING by "
    "default, which is scaffolding rather than coverage: it exists so the blocking lanes run "
    "with the gate PRESENT rather than bypassed, and so the recorded answering suites keep "
    "passing unedited. Every refusing branch is driven by a row that constructs its own "
    "verdict, and the live legs are where a real judge meets the real defect."
)

**Why affirm-by-default is safe here and would not be anywhere else.** The recorded suites'
must-decline cases already decline *before* this judge is reached — their invented anchors fail
citation resolution, so `kept` is empty and the gate is never invoked. What the default preserves
is the answering cases that legitimately answer today (SC-003). What it must never do is stand in
for the gate's teeth, which is why `affirms`, `unreachable` and `malformed` exist and why the
contract says so in its own header.
"""

from __future__ import annotations

from collections.abc import Sequence

from core.answering.relevance import (
    RelevanceRefused,
    RelevanceVerdict,
    parse_verdict,
)

DECLARED_FAKE_RELEVANCE_JUDGE = (
    "Affirms by default so the blocking lanes run with the gate present; every refusing "
    "branch is driven by a row that constructs its own verdict."
)

FIXTURE_MODEL = "fixture/relevance@1"


class FixtureRelevanceJudge:
    """Deterministic, countable, and able to fail on request."""

    def __init__(
        self,
        *,
        affirms: Sequence[int] | None = None,
        affirm_none: bool = False,
        unreachable: bool = False,
        unqualified: bool = False,
        malformed: bool = False,
        model: str = FIXTURE_MODEL,
    ) -> None:
        #: Zero-based indices to affirm. None means "all of them" — the default.
        self._affirms = None if affirms is None else frozenset(affirms)
        self._affirm_none = affirm_none
        self._unreachable = unreachable
        self._unqualified = unqualified
        self._malformed = malformed
        self._model = model
        #: How many times the gate actually ran. R5 asserts this stays zero when every claim
        #: failed citation resolution — a cost bound proven by counting rather than by reading.
        self.calls = 0
        self.last_claims: tuple[str, ...] = ()

    def assess(self, question: str, claims: Sequence[str]) -> RelevanceVerdict:
        self.calls += 1
        self.last_claims = tuple(claims)

        if self._unreachable:
            raise RelevanceRefused(
                "the relevance judge could not be reached",
                reason_code="relevance_unavailable",
            )
        if self._unqualified:
            raise RelevanceRefused(
                "the relevance cell is not qualified",
                reason_code="unqualified_cell",
            )
        if self._malformed:
            # Through the REAL parser, so the row exercises the production refusal rather than
            # a fixture's idea of one.
            return parse_verdict(
                "I think claims one and three are on point.",
                claim_count=len(claims),
                model=self._model,
            )
        if self._affirm_none:
            return parse_verdict("RELEVANT: none", claim_count=len(claims), model=self._model)

        indices = range(len(claims)) if self._affirms is None else sorted(self._affirms)
        body = ",".join(str(index + 1) for index in indices) or "none"
        return parse_verdict(f"RELEVANT: {body}", claim_count=len(claims), model=self._model)


__all__ = ["DECLARED_FAKE_RELEVANCE_JUDGE", "FIXTURE_MODEL", "FixtureRelevanceJudge"]
