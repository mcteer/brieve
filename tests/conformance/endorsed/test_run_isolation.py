# SPDX-License-Identifier: Apache-2.0
"""E15–E17 — a run keeps the ground it started on (045, T017, US4).

**The failure this phase exists to prevent is invisible.** A run whose ground moved mid-flight
does not crash: it finishes, cites correctly, and rests on content adopted after it began. The
only place the discrepancy shows is a record that names one version while the run read another
— so these rows assert the version, not the outcome.

**Two mechanisms, because the two paths differ.** An ask is one short request and resolves once,
which gives it isolation for free. A dispatched run outlives the resolution, so it pins the
identity into the checkpoint payload at start and a resumed run reads *that* rather than
re-resolving to current. The exact parallel of "re-authenticates, never replays": the authority
is fetched fresh on resume and the ground deliberately is not.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.answering.endorsed.corpus import (
    CombinedCorpus,
    build_endorsed_corpus,
    resolve_endorsed,
)
from core.answering.endorsed.records import (
    ADOPTED,
    EndorsedDocument,
    SyncedVersion,
    digest_of_document,
)
from core.durability.checkpoint import (
    ENDORSED_VERSION_KEY,
    checkpoint_run,
    pinned_endorsed_version,
)

OLD_PATH = "/endorsed/acme-standards/logging.md"
NEW_PATH = "/endorsed/acme-standards/incident.md"


def _document(path: str) -> EndorsedDocument:
    sections = {"scope": f"content of {path}"}
    return EndorsedDocument(
        path=path,
        url=f"https://git.example.com{path}",
        digest=digest_of_document(sections),
        anchors=frozenset(sections),
        sections=dict(sections),
    )


def _version(version_id: str, paths: list[str]) -> SyncedVersion:
    return SyncedVersion(
        version_id=version_id,
        tenant_id="acme",
        source="acme-standards",
        upstream_tip=version_id,
        synced_at=datetime(2026, 8, 1, tzinfo=UTC),
        synced_by="dan@acme.example",
        state=ADOPTED,
        documents={path: _document(path) for path in paths},
    )


class _Store:
    def __init__(self) -> None:
        self.versions = {
            "v-one": _version("v-one", [OLD_PATH]),
            "v-two": _version("v-two", [OLD_PATH, NEW_PATH]),
        }

    def read_version(self, version_id: str, *, verify: bool = True) -> SyncedVersion | None:
        return self.versions.get(version_id)


def _record(adopted: str) -> dict[str, Any]:
    return {
        "acme-standards": {
            "location": "https://git.example.com/acme/standards",
            "endorsed_by": "dan@acme.example",
            "adopted_version": adopted,
        }
    }


# ── E15: a run started before an adoption completes on its original version ───────────────


def test_row_e15_two_asks_across_an_adoption_see_different_ground_in_one_process() -> None:
    """The ask path's isolation, and it is a property of resolving once.

    Both resolutions happen in one process against one store — no restart, no reload — so what
    separates them is the adoption and nothing else. An implementation that cached the corpus
    would pass a two-process version of this row and fail here.
    """
    store = _Store()
    record = _record("v-one")

    before = resolve_endorsed(read_sources=lambda: record, store=store, tenant_id="acme")
    assert before.digest == "v-one"
    assert not before.resolves(NEW_PATH, "scope")

    record["acme-standards"]["adopted_version"] = "v-two"

    after = resolve_endorsed(read_sources=lambda: record, store=store, tenant_id="acme")
    assert after.digest == "v-two"
    assert after.resolves(NEW_PATH, "scope")


def test_row_e15_an_answer_in_flight_holds_the_corpus_it_was_handed() -> None:
    """The mechanism, stated as what it is: one resolution per request, handed downstream.

    `answer_question` is given a corpus. It has no reader, no store and no way to re-resolve —
    which is what makes "the ground cannot move under a single answer" structural rather than a
    matter of how fast the answer came back.
    """
    store = _Store()
    record = _record("v-one")
    corpus = CombinedCorpus(
        pinned=None, endorsed=resolve_endorsed(read_sources=lambda: record, store=store)
    )

    record["acme-standards"]["adopted_version"] = "v-two"

    assert corpus.endorsed_version == "v-one"
    assert not corpus.resolves(NEW_PATH, "scope")


# ── E16: across a resume — interrupted before, resumed after, still on the original ────────


class _Provider:
    def __init__(self) -> None:
        self.saved: list[Any] = []

    def save(self, blob: Any) -> None:
        self.saved.append(blob)

    def load(self, blob_id: str) -> Any:
        return self.saved[-1] if self.saved else None


class _Run:
    """The fields `checkpoint_run` reads. Not a `GovernedRun` — this row is about one function.

    Constructing a full run would drag identity, a registry and an audit sink into a row whose
    subject is whether one key survives a payload replacement.
    """

    def __init__(self, endorsed_version: str) -> None:
        self.durability = _Provider()
        self.lease = None
        self.run_id = "run-1"
        self.correlation_id = "corr-1"
        self.grant = None
        self.step_index = 0
        self.resume_count = 0
        self.endorsed_version = endorsed_version


def test_row_e16_the_pin_survives_every_step_checkpoint() -> None:
    """**The defect this row is written against, stated plainly.**

    Every step checkpoint passes `payload={"step": n}`, which REPLACES the payload. A pin
    written once at run start would live until the first step and then be gone; the resumed run
    would re-resolve to whatever is currently adopted, finish, and cite content adopted after
    it began. Nothing would look wrong at any point.
    """
    run = _Run("v-one")

    checkpoint_run(run, payload={"step": 0})  # type: ignore[arg-type]
    run.step_index = 1
    checkpoint_run(run, payload={"step": 1})  # type: ignore[arg-type]

    assert pinned_endorsed_version(run.durability.saved[-1]) == "v-one"
    assert run.durability.saved[-1].payload["step"] == 1


def test_row_e16_a_resumed_run_loads_its_pinned_version_not_the_current_one() -> None:
    """The resume half. What was adopted since is irrelevant to a run already under way."""
    store = _Store()
    record = _record("v-two")  # the estate has moved on
    blob = type("Blob", (), {"payload": {ENDORSED_VERSION_KEY: "v-one", "step": 3}})()

    resumed = resolve_endorsed(
        read_sources=lambda: record,
        store=store,
        pinned_version=pinned_endorsed_version(blob),
    )

    assert resumed.digest == "v-one"
    assert not resumed.resolves(NEW_PATH, "scope")
    # And the record it will not consult would have said otherwise.
    assert resolve_endorsed(read_sources=lambda: record, store=store).digest == "v-two"


def test_row_e16_a_run_with_no_pin_resolves_current_rather_than_nothing() -> None:
    """A run that started before this feature, or in an estate with nothing endorsed.

    It must resolve normally rather than be treated as pinned-to-nothing — otherwise the first
    resume after an upgrade would quietly stop citing customer material.
    """
    store = _Store()
    blob = type("Blob", (), {"payload": {"step": 3}})()

    assert pinned_endorsed_version(blob) == ""
    assert (
        resolve_endorsed(
            read_sources=lambda: _record("v-two"), store=store, pinned_version=""
        ).digest
        == "v-two"
    )


def test_row_e16_a_pinned_version_that_no_longer_exists_resolves_nothing() -> None:
    """Superseded versions are retained (research R3) precisely so this does not happen — and
    if retention is ever changed, this is what fails.

    Resolving nothing is the safe direction: the run's citations stop resolving and it declines,
    rather than silently answering from a different version than its record names.
    """
    store = _Store()

    resumed = resolve_endorsed(
        read_sources=lambda: _record("v-two"), store=store, pinned_version="v-deleted"
    )

    assert resumed.empty
    assert resumed.digest == ""


# ── E17: every record names exactly one content identity ──────────────────────────────────


def test_row_e17_a_corpus_reports_one_endorsed_version_however_many_sources() -> None:
    """FR-017h. A record naming two is a run whose ground moved underneath it.

    With several sources endorsed the identity is a digest over the contributing versions, so
    "one value" survives the case that would most naturally have produced a list.
    """
    other = SyncedVersion(
        version_id="v-other",
        tenant_id="acme",
        source="acme-policies",
        upstream_tip="zzz",
        synced_at=datetime(2026, 7, 1, tzinfo=UTC),
        synced_by="dan@acme.example",
        state=ADOPTED,
        documents={"/endorsed/acme-policies/p.md": _document("/endorsed/acme-policies/p.md")},
    )

    corpus = build_endorsed_corpus([_version("v-one", [OLD_PATH]), other])

    assert isinstance(corpus.digest, str)
    assert corpus.digest
    assert corpus.resolves(OLD_PATH, "scope")
    assert corpus.resolves("/endorsed/acme-policies/p.md", "scope")


def test_row_e17_the_pinned_digest_and_the_endorsed_version_stay_separate() -> None:
    """Two fields, two provenances, one record — research R1's rejected alternative, asserted."""

    class _Pinned:
        digest = "corpus-digest"
        synced_at = datetime(2026, 8, 1, tzinfo=UTC)
        documents: dict[str, Any] = {}

        def resolves(self, path: str, anchor: str) -> bool:
            return False

        def url_for(self, path: str, anchor: str) -> str:
            return ""

    combined = CombinedCorpus(
        pinned=_Pinned(), endorsed=build_endorsed_corpus([_version("v-one", [OLD_PATH])])
    )

    assert combined.digest == "corpus-digest"
    assert combined.endorsed_version == "v-one"
    assert combined.digest != combined.endorsed_version


def test_the_disclosed_age_is_the_older_of_the_two() -> None:
    """FR-017b. The disclosure must describe the staleness a reader could be affected by.

    Reporting the fresher would let a corpus re-pinned this morning vouch for the currency of
    customer material synced months ago — a currency claim the platform has not earned.
    """

    class _Pinned:
        digest = "corpus-digest"
        synced_at = datetime(2026, 8, 1, tzinfo=UTC)
        documents: dict[str, Any] = {}

        def resolves(self, path: str, anchor: str) -> bool:
            return False

        def url_for(self, path: str, anchor: str) -> str:
            return ""

    older = SyncedVersion(
        version_id="v-old",
        tenant_id="acme",
        source="acme-standards",
        upstream_tip="aaa",
        synced_at=datetime(2026, 1, 1, tzinfo=UTC),
        synced_by="dan@acme.example",
        state=ADOPTED,
        documents={OLD_PATH: _document(OLD_PATH)},
    )

    combined = CombinedCorpus(pinned=_Pinned(), endorsed=build_endorsed_corpus([older]))

    assert combined.synced_at == datetime(2026, 1, 1, tzinfo=UTC)


def test_with_nothing_endorsed_the_disclosed_age_is_the_pins_own() -> None:
    """US6 at the disclosure layer: an estate that endorsed nothing discloses what it always did."""

    class _Pinned:
        digest = "corpus-digest"
        synced_at = datetime(2026, 8, 1, tzinfo=UTC)
        documents: dict[str, Any] = {}

        def resolves(self, path: str, anchor: str) -> bool:
            return False

        def url_for(self, path: str, anchor: str) -> str:
            return ""

    combined = CombinedCorpus(pinned=_Pinned())

    assert combined.synced_at == datetime(2026, 8, 1, tzinfo=UTC)
