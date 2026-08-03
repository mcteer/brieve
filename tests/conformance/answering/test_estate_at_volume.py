# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — an estate question at real volume is answered from records about it.

**The row that would have caught the finding.** Every prior estate row exercises tens of records,
where a thousand-row bound never truncates and every window is every record. The deployed tenant
holds 236,581 readable entries, and the first question a person asked it — *"What ran today?"* —
routed correctly, obtained a credential, reached the evidence plane, and declined. The read had
returned 1,000 of 63,947 entries composed as `effect_observed` 383, `pre_decision` 302, …
`run_start` 60. Sixty run records under 940 pieces of per-step machinery. Every layer behaved
correctly on the evidence it was given.

**The defect is competition, not size**, which is why this row asserts a property no larger number
could buy: at a skew where the noisy type outnumbers the question's type ten to one, the answer
still rests on the question's records.

**Driven through the full ask path**, not against the query alone — the read's bound, the focus
composition, the scope intersection and the answer's window note are four things that must line
up, and a row that exercised one would prove nothing about the other three.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from core.audit.schema import AuditEventType
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

MODEL = "anthropic/claude-opus@5"


def _within_today(count: int) -> list[datetime]:
    """`count` ascending timestamps inside the window *"today"* resolves to, at run time.

    **Not a fixed date, and the first version of this file was.** The question these rows exist
    for is *"What ran today?"*, whose window resolves against the wall clock — so a fixture pinned
    to a calendar date passes on the day it was written and fails afterwards. It did: green
    locally, red in CI seven minutes past midnight UTC the next day, with the records a day
    outside the window they were meant to be inside.

    That is the same ambient-time hazard `routing.py` names when it explains why window phrases are
    *recognised* in core and *resolved* by the caller against an injected clock. A row cannot
    inject through HTTP, so it places its records relative to the clock the route will read.

    The span is capped at the time actually elapsed since midnight, so the fixture stays inside
    the window even when a run starts seconds after it.
    """
    now = datetime.now(UTC)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    span = min(timedelta(minutes=30), now - day_start)
    step = span / max(count, 1)
    return [now - span + step * i for i in range(count)]


#: The live composition's ratio: the noisiest type against the one a runs question needs.
#: Measured 383:60; rounded here to a clean 10:1, which is if anything gentler than reality.
NOISE_PER_RUN = 10
RUNS = 120


class _CitesWhatItWasGiven:
    """Cites the first record it receives, whatever type that is.

    The point of the row is *which records reach the model*, so the double must not be clever
    about them — a provider that searched for run records would hide the starvation this exists
    to detect.
    """

    def __init__(self) -> None:
        self.seen: list[AuditEventType] = []

    def answer(self, question: str, material: Any) -> list[dict[str, Any]]:
        from core.answering.corpus import Corpus

        if isinstance(material, Corpus):
            return [{"statement": "From the corpus.", "citations": []}]
        self.seen = [r.event_type for r in material]
        return [
            {
                "statement": "A run was recorded.",
                "references": [{"entry_hash": r.entry_hash} for r in material[:1]],
            }
        ]


def _tenant_at_volume(surface: Any) -> None:
    """A day's activity with the live tenant's shape: loud step machinery, quieter runs."""
    total = RUNS * (NOISE_PER_RUN + 1)
    stamps = _within_today(total)
    index = 0
    for i in range(RUNS):
        for _ in range(NOISE_PER_RUN):
            surface.audit.append_event(
                correlation_id=f"noise-{index:06d}",
                tenant_id="tenant-test",
                event_type=AuditEventType.EFFECT_OBSERVED,
                payload={"index": index},
                timestamp=stamps[index],
            )
            index += 1
        surface.audit.append_event(
            correlation_id=f"run-{i:05d}",
            tenant_id="tenant-test",
            event_type=AuditEventType.RUN_START,
            payload={"index": index, "subject_user_id": "alice"},
            timestamp=stamps[index],
        )
        index += 1


def _answering_surface(provider: Any) -> Any:
    return surface_under_test(
        ask_provider=provider,
        ask_model=MODEL,
        ask_authority=qualified_ask_authority(model=MODEL),
        credential_source=available_credential(),
    )


def test_a_runs_question_is_answered_from_run_records() -> None:
    """SC-002, in the exact shape that failed against the deployed platform.

    The noisy type outnumbers run records ten to one. Under a shared row-count bound the model
    receives overwhelmingly noise; under a per-type bound it receives the runs the question is
    about. Asserted on the composition the provider actually saw, because that is the thing the
    model had to answer from.
    """
    provider = _CitesWhatItWasGiven()
    surface = _answering_surface(provider)
    _tenant_at_volume(surface)

    response = TestClient(surface.app).post(
        "/ask", json={"question": "What ran today?"}, headers=surface.bearer()
    )

    assert response.status_code == 200
    assert provider.seen, "the provider received no records at all"
    runs = sum(1 for kind in provider.seen if kind is AuditEventType.RUN_START)
    noise = sum(1 for kind in provider.seen if kind is AuditEventType.EFFECT_OBSERVED)
    assert runs > noise, (
        f"a question about runs was answered from {runs} run records and {noise} pieces of step "
        f"machinery; the estate's noisiest activity is still winning the window"
    )
    assert runs == RUNS, f"the run records were themselves truncated: {runs} of {RUNS}"


def test_the_answer_says_when_it_rested_on_a_window() -> None:
    """FR-006 through the full path: the asker learns they were shown a slice.

    **The note appears when the QUESTION'S OWN type truncates**, which is later than one might
    expect and is the point. At the previous row's volume the noise is excluded by focus rather
    than truncated, so nothing is a window and the answer carries no caveat — correctly. A note
    naming a type the question was never about would be noise of a different kind.

    So this row pushes past the per-type bound on run records themselves: more runs than any
    single answer may rest on, and the note says which slice arrived of how many.
    """
    from surfaces.api.ask import RECORDS_PER_TYPE

    surface = _answering_surface(_CitesWhatItWasGiven())
    total_runs = RECORDS_PER_TYPE + 50
    for i, stamp in enumerate(_within_today(total_runs)):
        surface.audit.append_event(
            correlation_id=f"run-{i:05d}",
            tenant_id="tenant-test",
            event_type=AuditEventType.RUN_START,
            payload={"index": i, "subject_user_id": "alice"},
            timestamp=stamp,
        )

    body = (
        TestClient(surface.app)
        .post("/ask", json={"question": "What ran today?"}, headers=surface.bearer())
        .json()
    )

    note = body.get("window_note", "")
    assert note.startswith("Based on "), f"a truncated answer carried no window note: {note!r}"
    assert f"{RECORDS_PER_TYPE} most recent" in note, note
    assert f"of {total_runs}" in note, (
        f"the note does not say how many existed, so a reader cannot tell how partial the "
        f"answer is: {note!r}"
    )


def test_a_small_estate_answers_without_a_caveat() -> None:
    """The common case, and the one a careless note would spoil.

    Below the bound nothing is a window, so the answer must carry no caveat at all — an
    unconditional note would teach readers to ignore it, which costs exactly the case it exists
    for.
    """
    surface = _answering_surface(_CitesWhatItWasGiven())
    for i, stamp in enumerate(_within_today(3)):
        surface.audit.append_event(
            correlation_id=f"run-{i}",
            tenant_id="tenant-test",
            event_type=AuditEventType.RUN_START,
            payload={"index": i, "subject_user_id": "alice"},
            timestamp=stamp,
        )

    body = (
        TestClient(surface.app)
        .post("/ask", json={"question": "What ran today?"}, headers=surface.bearer())
        .json()
    )

    assert body.get("window_note", "") == ""


def test_the_read_never_returns_a_type_outside_the_askers_scope() -> None:
    """FR-005 at volume, where a windowing defect could most easily hide.

    Focus narrows within what the role may see. If the composition ever widened, the extra type
    would arrive among thousands of legitimate records and look like nothing at all — so the row
    checks what the provider received rather than what the request asked for.
    """
    from core.answering.scope import visible_event_types

    provider = _CitesWhatItWasGiven()
    surface = _answering_surface(provider)
    _tenant_at_volume(surface)
    surface.audit.append_event(
        correlation_id="denied-1",
        tenant_id="tenant-test",
        event_type=AuditEventType.AUTHORITY_DENIED,
        payload={"subject_user_id": "alice"},
        timestamp=_within_today(1)[0],
    )

    TestClient(surface.app).post(
        "/ask", json={"question": "What ran today?"}, headers=surface.bearer()
    )

    visible = visible_event_types(frozenset({"operator"}))
    outside = {kind for kind in provider.seen if kind not in visible}
    assert outside == set(), f"the read returned types this role may not see: {outside}"
    assert AuditEventType.AUTHORITY_DENIED not in provider.seen
