# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — an estate answer rests only on records the asker was shown.

The rows that matter here are the ones where the path returns **less** than the model proposed: a
reference that does not resolve, an answer that adjudicates, a provider that failed. Each is a way
the path could quietly become more helpful and less honest.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.answering.estate import (
    ANSWERED,
    DECLINED,
    EstateProviderUnavailable,
    RecordedEstateProvider,
    VerdictRefused,
    answer_estate_question,
)
from core.audit.schema import AuditEntry, AuditEventType


def _entry(seq: int, event_type: AuditEventType = AuditEventType.RUN_START) -> AuditEntry:
    return AuditEntry(
        tenant_id="tenant-a",
        correlation_id="run-1",
        seq=seq,
        event_type=event_type,
        timestamp=datetime(2026, 8, 1, 3, seq, tzinfo=UTC),
        payload={"outcome": "allow"},
        prev_hash="0" * 64,
        entry_hash=f"hash-{seq}",
    )


RECORDS = (_entry(1), _entry(2))


class _Provider:
    """Returns exactly the candidates it was given."""

    def __init__(self, *candidates: dict[str, Any]) -> None:
        self._candidates = list(candidates)

    def answer(self, question: str, records: tuple[AuditEntry, ...]) -> list[dict[str, Any]]:
        return self._candidates


def _claim(statement: str, *hashes: str) -> dict[str, Any]:
    return {"statement": statement, "references": [{"entry_hash": h} for h in hashes]}


def test_a_claim_whose_references_resolve_survives() -> None:
    answer = answer_estate_question(
        question="What changed last night?",
        records=RECORDS,
        provider=_Provider(_claim("Two runs started.", "hash-1", "hash-2")),
    )
    assert answer.disposition == ANSWERED
    assert len(answer.claims) == 1
    assert answer.source == "estate"


def test_one_unresolvable_reference_drops_the_whole_claim() -> None:
    """Partly-supported is not supported.

    A claim resting on two records where one was never shown to this asker is a claim about
    something outside their scope, and shipping it with the resolvable half attached would make it
    look verified.
    """
    answer = answer_estate_question(
        question="What changed last night?",
        records=RECORDS,
        provider=_Provider(_claim("Two runs started.", "hash-1", "hash-999")),
    )
    assert answer.disposition == DECLINED
    assert answer.dropped == ("Two runs started.",)


def test_a_claim_with_no_reference_at_all_is_dropped() -> None:
    answer = answer_estate_question(
        question="What changed last night?",
        records=RECORDS,
        provider=_Provider(_claim("Trust me, nothing happened.")),
    )
    assert answer.disposition == DECLINED
    assert answer.dropped == ("Trust me, nothing happened.",)


def test_the_decline_names_the_records_never_the_corpus() -> None:
    """FR-010c. Somebody who asked about their estate must not be sent to documentation."""
    answer = answer_estate_question(
        question="What changed last night?",
        records=(),
        provider=_Provider(),
    )
    assert answer.disposition == DECLINED
    assert "records" in answer.declined_reason
    assert "corpus" not in answer.declined_reason.lower()


def test_an_empty_scope_declines_exactly_like_a_scope_with_nothing_relevant() -> None:
    """SC-008's response half — the caller cannot tell "nothing" from "not yours".

    Both produce the same disposition AND the same reason. A difference in either would be an
    existence oracle: ask, compare the wording, learn whether records you may not see exist.
    """
    nothing_visible = answer_estate_question(
        question="What changed last night?", records=(), provider=_Provider()
    )
    nothing_relevant = answer_estate_question(
        question="What changed last night?", records=RECORDS, provider=_Provider()
    )
    assert nothing_visible.disposition == nothing_relevant.disposition
    assert nothing_visible.declined_reason == nothing_relevant.declined_reason


def test_a_provider_fault_raises_rather_than_declining() -> None:
    """FR-003. "The records do not show this" and "we could not read them" differ."""

    class _Broken:
        def answer(self, question: str, records: tuple[AuditEntry, ...]) -> list[dict[str, Any]]:
            raise RuntimeError("the store went away")

    with pytest.raises(EstateProviderUnavailable):
        answer_estate_question(
            question="What changed last night?", records=RECORDS, provider=_Broken()
        )


@pytest.mark.parametrize(
    "verdict",
    [
        "Your estate is compliant with the control.",
        "The production workspace is healthy.",
        "This configuration is secure.",
    ],
)
def test_an_answer_that_adjudicates_is_refused(verdict: str) -> None:
    """SC-003, FR-005 — evidence with citations, never a verdict.

    Checked over the ASSEMBLED answer rather than the provider's output, because that is where the
    temptation lives: the claim is perfectly referenced, and it still says something the platform
    has no standing to say.
    """
    with pytest.raises(VerdictRefused):
        answer_estate_question(
            question="Are we compliant?",
            records=RECORDS,
            provider=_Provider(_claim(verdict, "hash-1")),
        )


def test_reporting_what_the_records_show_is_not_a_verdict() -> None:
    """The distinction has to cut somewhere, and it cuts at adjudication.

    "Three applies were denied" is a fact with a reference. "You are compliant" is a judgement.
    A check that refused both would make the feature useless; one that refused neither would make
    it dishonest.
    """
    answer = answer_estate_question(
        question="What changed last night?",
        records=RECORDS,
        provider=_Provider(_claim("Two runs started and neither was denied.", "hash-1")),
    )
    assert answer.disposition == ANSWERED


def test_a_product_configuration_question_declines_plainly() -> None:
    """FR-006b (analysis C2).

    The evidence plane does not hold mount tables. This behaviour lives in a component row because
    the eval suite structurally cannot carry decline cases — fidelity over an empty expected set
    passes vacuously, so `events` is required non-empty there.
    """
    answer = answer_estate_question(
        question="Which secrets engines are mounted?",
        records=RECORDS,
        provider=_Provider(),
    )
    assert answer.disposition == DECLINED
    assert "records" in answer.declined_reason


def test_the_recorded_provider_names_records_by_authored_id() -> None:
    """Analysis U3 — a case author writes `rec-vault-001`, never a content hash."""
    provider = RecordedEstateProvider(
        "Two runs started, per rec-vault-001.", {"rec-vault-001": "hash-1"}
    )
    answer = answer_estate_question(
        question="What changed last night?", records=RECORDS, provider=provider
    )
    assert answer.disposition == ANSWERED
    assert answer.claims[0].references[0].entry_hash == "hash-1"


def test_an_authored_id_with_no_mapping_does_not_resolve() -> None:
    """A case naming a record the fixture estate lacks fails, rather than half-passing."""
    provider = RecordedEstateProvider("Per rec-does-not-exist.", {"rec-vault-001": "hash-1"})
    answer = answer_estate_question(
        question="What changed last night?", records=RECORDS, provider=provider
    )
    assert answer.disposition == DECLINED


# --------------------------------------------------------------- US2: windows


def test_a_window_phrase_narrows_against_the_injected_clock() -> None:
    """US2. "Last night" is resolved from the clock the caller supplies, never from ambient time.

    Ambient time inside an answering path is how an eval lane stops being reproducible — the same
    hazard the workflow runtime bans `Date.now()` for. The caller passes `now`; core reads no clock.
    """
    from surfaces.api.ask import _window

    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    start, end = _window("What changed last night?", now)

    assert start is not None and end is not None
    assert start < end
    assert start.date() == datetime(2026, 8, 1, tzinfo=UTC).date()


def test_the_same_phrase_resolves_identically_for_the_same_clock() -> None:
    """Determinism, which is what makes a window row scorable rather than flaky."""
    from surfaces.api.ask import _window

    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    assert _window("What changed yesterday?", now) == _window("What changed yesterday?", now)


def test_an_unrecognised_phrase_falls_back_to_the_reads_own_bound() -> None:
    """No general time parsing (analysis U4).

    A window guessed wrong returns records from the wrong period while looking entirely correct,
    so an unrecognised phrase yields no bounds and the read's `limit` bounds it instead.
    """
    from surfaces.api.ask import _window

    now = datetime(2026, 8, 2, 12, tzinfo=UTC)
    assert _window("What changed during the last fiscal quarter?", now) == (None, None)
    assert _window("Which runs were denied?", now) == (None, None)


def test_a_question_about_all_time_is_bounded_rather_than_unbounded() -> None:
    """The spec's "enormous window" edge case.

    No bounds is not unbounded: the governed read carries `limit`, so the worst case is a bounded
    read rather than a scan of the whole trail.
    """
    from core.audit.query import EvidenceQueryRequest

    assert EvidenceQueryRequest(tenant_id="t").limit > 0
