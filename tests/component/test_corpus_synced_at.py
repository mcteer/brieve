# SPDX-License-Identifier: Apache-2.0
"""The pin records when it was made — and every way of not knowing that is one state.

**Why `None` rather than an exception, asserted rather than commented.** The failure this
feature guards is an answer claiming currency it has not earned. A loader that refused to
load over a malformed date would take answering down for a metadata field; returning `None`
makes the answer say it cannot vouch for its ground's age. That is fail-closed on the thing
that matters, and these rows are where the direction is pinned.

The committed 33-document corpus has no timestamp and never will — it was pinned before
anything recorded one. It must keep answering, which is what lets this feature merge before
the first re-sync ever runs.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.answering.corpus import CorpusUnavailable, load_corpus

ROOT = Path(__file__).resolve().parents[2]
REAL_MANIFEST = ROOT / "corpus" / "manifest.json"
REAL_DOCUMENTS = ROOT / "corpus" / "documents"


def _manifest_with(tmp_path: Path, **overrides: object) -> Path:
    """The real manifest, one field changed — so these rows exercise the real shape."""
    data = json.loads(REAL_MANIFEST.read_text())
    for key, value in overrides.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    written = tmp_path / "manifest.json"
    written.write_text(json.dumps(data))
    return written


def _load(manifest: Path) -> object:
    return load_corpus(manifest=manifest, documents_dir=REAL_DOCUMENTS, verify=False)


def test_the_committed_pin_loads_with_no_sync_time() -> None:
    """FR-009. The 024 corpus answers on the day this lands, disclosing unknown age."""
    corpus = load_corpus()

    assert corpus.documents, "the committed corpus loaded empty"
    assert corpus.synced_at is None, (
        "the committed pin reports a sync time it does not carry — the unknown state is what "
        "lets this feature merge before the first re-sync"
    )


def test_a_well_formed_sync_time_is_parsed(tmp_path: Path) -> None:
    pinned = datetime(2026, 8, 3, 12, 30, tzinfo=UTC)
    corpus = _load(_manifest_with(tmp_path, synced_at=pinned.isoformat()))

    assert corpus.synced_at == pinned


@pytest.mark.parametrize(
    ("label", "value"),
    [
        ("absent", None),
        ("empty", ""),
        ("whitespace", "   "),
        ("not a date", "last Tuesday"),
        ("wrong type", 1785000000),
        ("naive — no zone to trust", "2026-08-03T12:30:00"),
    ],
)
def test_every_unknowable_sync_time_loads_as_unknown(
    tmp_path: Path, label: str, value: object
) -> None:
    """One state, six ways in. A naive timestamp counts: it is not comparable to an aware
    `now`, and guessing its zone would be inventing provenance."""
    corpus = _load(_manifest_with(tmp_path, synced_at=value))

    assert corpus.synced_at is None, f"a {label} sync time did not read as unknown"


def test_a_future_sync_time_is_unknown_not_very_fresh(tmp_path: Path) -> None:
    """Clock skew at sync produces one. Reading it as freshness is the single direction that
    would let an unfounded currency claim through, so it reads as unknown."""
    ahead = (datetime.now(UTC) + timedelta(days=2)).isoformat()

    corpus = _load(_manifest_with(tmp_path, synced_at=ahead))

    assert corpus.synced_at is None


def test_a_malformed_sync_time_never_raises(tmp_path: Path) -> None:
    """The direction of the fail-closed argument, stated as a row.

    A corpus whose CONTENT does not match its pin still refuses — that is a citation pointing
    at nothing. A corpus whose metadata is unreadable answers, and discloses. The two are
    different failures and this row keeps them from being confused by a later edit.
    """
    manifest = _manifest_with(tmp_path, synced_at="not-a-date")

    corpus = _load(manifest)
    assert corpus.synced_at is None

    broken = json.loads(manifest.read_text())
    broken["documents"][0]["anchors"] = ["an-anchor-that-is-not-in-the-vendored-content"]
    (tmp_path / "broken.json").write_text(json.dumps(broken))
    with pytest.raises(CorpusUnavailable):
        load_corpus(manifest=tmp_path / "broken.json", documents_dir=REAL_DOCUMENTS, verify=True)
