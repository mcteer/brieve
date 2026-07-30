# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — the run record names what was read, and keeps naming it (FR-021, SC-008).

**The row that matters is the second one.** Recording a URL and a hash is easy; the property
is that the record *does not follow the guidance* when the guidance changes. A run that
consulted a page in March must, in December, still be attributable to the March text — not
to whatever is at that URL now.

That is the whole of ADR-0030's consulted half. Fetching fresh is right, and it is precisely
what makes the record necessary.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.packs.consulted import (
    ConsultedArtifact,
    FixtureGuidance,
    GuidanceUnavailable,
    archive,
    consult,
)

URL = "https://developer.hashicorp.com/validated-patterns/example"
SALT = b"a" * 32
OTHER_SALT = b"b" * 32


def _source() -> FixtureGuidance:
    return FixtureGuidance({URL: "Guidance as published in March."})


def test_the_triple_is_archived() -> None:
    source = _source()
    _, record = consult(URL, source=source, run_salt=SALT)

    assert record.url == URL
    assert record.read_at.endswith("Z"), "timestamp is not RFC 3339 UTC like the audit chain"
    assert record.content_hash


def test_changing_the_guidance_afterwards_does_not_change_the_record() -> None:
    """SC-008, and the reason this mechanism exists at all.

    The attestation must cite guidance **as published at the moment of the decision**, not
    as it stands at attestation time.
    """
    source = _source()
    _, march = consult(URL, source=source, run_salt=SALT)

    source.set(URL, "Guidance rewritten in December, saying something else entirely.")
    _, december = consult(URL, source=source, run_salt=SALT)

    assert march.content_hash != december.content_hash
    assert march.url == december.url, "the URL is the same; only what it said changed"


def test_the_record_carries_a_hash_and_never_the_text() -> None:
    """An unbounded external document must not become permanently resident in evidence.

    The trail is append-only. Archiving guidance text there would make the size of the
    evidence a function of how long someone else's documentation is.
    """
    source = FixtureGuidance({URL: "A very long document. " * 500})
    _, record = consult(URL, source=source, run_salt=SALT)

    payload = record.as_payload()
    assert "A very long document" not in str(payload)
    assert len(record.content_hash) == 64


def test_two_runs_reading_identical_guidance_produce_different_hashes() -> None:
    """Hashed under the run's own salt, like every other content hash here.

    Without the salt, a hash would be a stable fingerprint of a public document — and anyone
    holding one run's record could confirm what another run had read by comparing digests.
    """
    source = _source()
    _, one = consult(URL, source=source, run_salt=SALT)
    _, two = consult(URL, source=source, run_salt=OTHER_SALT)
    assert one.content_hash != two.content_hash


def test_unreachable_guidance_refuses_rather_than_resolving_to_empty() -> None:
    """Fresh sometimes means absent — the edge case the spec names.

    A run that "consulted" nothing and recorded a hash of the empty string would be attesting
    to a reading that never happened, which is worse than an error.
    """
    with pytest.raises(GuidanceUnavailable):
        consult("https://example.invalid/gone", source=_source(), run_salt=SALT)


def test_archiving_is_append_only_within_the_run_record() -> None:
    """An attestation that could lose a reading cannot say what the agent worked from."""
    source = _source()
    _, first = consult(URL, source=source, run_salt=SALT)
    second = ConsultedArtifact(
        url="https://other", read_at="2026-07-29T00:00:00.000000Z", content_hash="x"
    )

    record = archive(second, archive(first, {}))
    assert [c["url"] for c in record["consulted"]] == [URL, "https://other"]


def test_the_timestamp_matches_the_audit_chains_encoding() -> None:
    """One format, so an investigator is not comparing two across two records."""
    source = _source()
    _, record = consult(
        URL, source=source, run_salt=SALT, now=datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
    )
    assert record.read_at == "2026-07-29T12:00:00.000000Z"


def test_the_mechanism_is_proven_against_a_fixture_and_not_a_corpus() -> None:
    """**The honest limit, asserted rather than left in a docstring.**

    The validated-design corpus left with US6. Nothing in 013 gives an agent real guidance to
    read, so every row above proves the *mechanism* and none of them proves that consulting
    real guidance works. A green run here is not evidence of the second thing, and the class
    is named `FixtureGuidance` so it cannot be mistaken for a deployment option.
    """
    import core.packs.consulted as consulted

    concrete = [
        name
        for name in dir(consulted)
        if name.endswith("Guidance") and name not in {"FixtureGuidance", "GuidanceUnavailable"}
    ]
    assert not concrete, (
        f"a non-fixture guidance source exists: {concrete}. If a real corpus has landed, "
        f"update contracts/conformance-packs.md — it currently records that the mechanism is "
        f"proven and the corpus is not"
    )
