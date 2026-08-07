# SPDX-License-Identifier: Apache-2.0
"""The second corpus, and the view that composes it with the first (045, T006).

**This file is the whole of research R1.** The obvious design — a `tenant_id` threaded through
`load_corpus` — was rejected because it would make one reader serve two trust models: content
vendored through the supply chain and reviewed (ADR-0004), and content endorsed at runtime by
an administrator. Every check on the pinned side would then grow a branch for the endorsed
side, and `corpus.py`'s own docstring calls citation resolution *"the single most important
check in this feature"*. So there is a second implementation of the same contract, and
`corpus.py` is not edited at all — asserted as a diff, from this feature's first commit.

**The combined view is a composition, not a merge.** Resolution tries the pin, then the
endorsed set. A path can only ever live in one of them because every endorsed path begins
`/endorsed/`, which no validated-design path does — so overlap is structurally impossible
rather than a uniqueness check somebody has to remember to run.

**Nothing is fetched here either.** The endorsed reader reads a version that was synced
earlier, exactly as the pinned reader reads a manifest that was synced earlier. Answering makes
zero outbound requests, and a row asserts that by instrumentation rather than by the absence of
code (ADR-0070's bound, SC-003).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Protocol

from core.answering.endorsed.records import EndorsedDocument

#: Where a citation came from, emitted as **data** on every citation (research R2, clarify Q2).
#: Derivable from the path prefix and emitted explicitly anyway: deriving it in every consumer
#: is a convention, and 038's payload table records what conventions become.
VALIDATED_DESIGN: Final[str] = "validated-design"
CUSTOMER_ENDORSED: Final[str] = "customer-endorsed"

ENDORSED_PREFIX: Final[str] = "/endorsed/"


class Resolvable(Protocol):
    """The contract both corpora satisfy. Named so the composition can be typed.

    Structural rather than inherited, deliberately: a shared base class would be a seam through
    which a change made for customer content reaches the pinned reader, which is the coupling
    this feature exists to avoid.
    """

    def resolves(self, path: str, anchor: str) -> bool: ...

    def url_for(self, path: str, anchor: str) -> str: ...


@dataclass(frozen=True)
class EndorsedCorpus:
    """What a customer's endorsed material makes citable, at one adopted version.

    Same members as `Corpus` and none of its code. `digest` is the adopted `version_id` — the
    identity a run pins and a record names (FR-017h) — so a caller that already knows how to
    record which ground an answer rested on needs no new vocabulary.
    """

    #: The adopted `version_id`. Empty when nothing is adopted, which is a legitimate state:
    #: a source endorsed a minute ago and not yet synced is citable-in-principle and cites
    #: nothing, and that must not read as an error.
    digest: str = ""
    documents: dict[str, EndorsedDocument] = field(default_factory=dict)
    #: When the adopted version was synced. Drives the age disclosure through the same
    #: `describe_ground` reasoning the pinned corpus uses — customer material can be stale in
    #: exactly the way validated designs can.
    synced_at: datetime | None = None
    #: Which sources contributed, for the disclosure and for the review page.
    sources: frozenset[str] = frozenset()

    def resolves(self, path: str, anchor: str) -> bool:
        """The endorsed half of the check the whole feature turns on.

        Identical in shape to the pinned corpus's and separate in code. An unresolvable
        citation is worse than no citation *whoever endorsed the document*: it reads as
        evidence, and a reader who follows it and finds nothing has been told something false
        about what this platform knows.
        """
        document = self.documents.get(path)
        return document is not None and anchor in document.anchors

    def url_for(self, path: str, anchor: str) -> str:
        return f"{self.documents[path].url}#{anchor}"

    def text_at(self, path: str, anchor: str) -> str:
        document = self.documents.get(path)
        return document.text_at(anchor) if document else ""

    @property
    def empty(self) -> bool:
        return not self.documents


@dataclass(frozen=True)
class CombinedCorpus:
    """The pinned corpus and the endorsed corpus, consulted as one.

    **Composition, in this order, and the order does not matter for correctness** — the
    `/endorsed/` namespace makes the two disjoint — but it is fixed anyway so that behaviour
    never depends on which happens to be asked first. If the namespaces ever did overlap, the
    pin would win, which is the direction that cannot make a validated design uncitable.
    """

    pinned: Any
    endorsed: EndorsedCorpus = field(default_factory=EndorsedCorpus)

    @property
    def synced_at(self) -> Any:
        """The age the answer discloses: **the older of the two**, never the fresher (FR-017b).

        An answer can rest on both, and the disclosure must describe the staleness a reader
        could actually be affected by. Reporting the fresher would let a corpus re-pinned this
        morning vouch for the currency of customer material synced months ago — a currency
        claim the platform has not earned, which is the one direction `_parse_synced_at`'s own
        reasoning refuses.

        `None` from either side means unknown, and unknown wins: the pinned corpus has no
        timestamp and never will, and "age unknown" is what the answering path already
        discloses rather than inventing a date.
        """
        pinned = getattr(self.pinned, "synced_at", None)
        if self.endorsed.empty:
            return pinned
        if pinned is None or self.endorsed.synced_at is None:
            return None
        return min(pinned, self.endorsed.synced_at)

    def resolves(self, path: str, anchor: str) -> bool:
        if self.pinned is not None and self.pinned.resolves(path, anchor):
            return True
        return self.endorsed.resolves(path, anchor)

    def url_for(self, path: str, anchor: str) -> str:
        if self.pinned is not None and self.pinned.resolves(path, anchor):
            url: str = self.pinned.url_for(path, anchor)
            return url
        return self.endorsed.url_for(path, anchor)

    @property
    def documents(self) -> dict[str, Any]:
        """Both sets, for a caller that assembles context rather than checks a citation.

        The pinned documents first so an endorsed path could never shadow one — which it
        cannot anyway, and this makes that true of the mapping as well as of `resolves`.
        """
        merged: dict[str, Any] = dict(getattr(self.pinned, "documents", {}) or {})
        merged.update(self.endorsed.documents)
        return merged

    @property
    def digest(self) -> str:
        """The pinned corpus's digest, unchanged.

        The endorsed version is recorded **beside** `corpus_digest`, never folded into it. One
        digest covering content with two different trust stories is exactly what research R1
        rejected — the supply-chain scan would then either cover customer content, which is
        wrong, or exempt part of its own manifest, which is worse.
        """
        digest: str = getattr(self.pinned, "digest", "") or ""
        return digest

    @property
    def endorsed_version(self) -> str:
        return self.endorsed.digest


def resolve_endorsed(
    *,
    read_sources: Any,
    store: Any,
    tenant_id: str = "",
    pinned_version: str = "",
) -> EndorsedCorpus:
    """The endorsed corpus in force **right now**, or at a version a run already pinned (US4).

    **Once per request, and the ask path gets that for free.** One question is one resolution;
    there is no window during which a mid-request adoption could move the ground under a single
    answer. A dispatched run is the case that needs care, and `pinned_version` is how it gets
    it: resume passes the identity written into its checkpoint at start, and this loads *that*
    rather than re-resolving to whatever is current. The exact parallel of "re-authenticates,
    never replays" — the authority is fetched fresh, the ground is not.

    **Fails open to nothing, never to stale content.** Any failure returns an empty corpus:
    citations into customer material stop resolving and the answer declines or narrows, which
    is a visible, disclosed outcome. The alternative — carrying on with whatever was last
    loaded — would answer from content whose endorsement the platform could no longer confirm.
    """
    from core.authority.endorsed_sources import citable_sources

    if pinned_version:
        version = store.read_version(pinned_version)
        return build_endorsed_corpus([version] if version is not None else [])

    try:
        sources = citable_sources(read_sources())
    except Exception:  # noqa: BLE001 — an unreadable record resolves nothing; see the note
        return EndorsedCorpus()

    versions = []
    for name, source in sources.items():
        try:
            version = store.read_version(source.adopted_version)
        except Exception:  # noqa: BLE001 — one unreadable source must not silence the others,
            # and a digest mismatch on one body of material is not a reason to stop citing
            # everything else somebody endorsed.
            continue
        if version is not None and version.source == name:
            versions.append(version)

    return build_endorsed_corpus(versions)


def provenance_of(path: str) -> str:
    """Which corpus a citation path belongs to.

    One function, so the prefix convention has exactly one reader. Everything that renders,
    records or discloses a citation calls this rather than re-deriving it — the difference
    between a rule and a habit.
    """
    return CUSTOMER_ENDORSED if path.startswith(ENDORSED_PREFIX) else VALIDATED_DESIGN


def endorsed_path(source: str, relative: str) -> str:
    """Render the citation path for a document of an endorsed source.

    The single place the namespace is constructed, matching `provenance_of` as the single place
    it is read. A path assembled by string concatenation at a call site is how a document ends
    up outside the namespace that makes it distinguishable.
    """
    return f"{ENDORSED_PREFIX}{source}/{relative.lstrip('/')}"


def build_endorsed_corpus(versions: list[Any]) -> EndorsedCorpus:
    """Compose the adopted versions of several sources into one reader.

    Several sources, one corpus: an administrator endorses sources independently and an answer
    should not have to know which of them a document came from in order to cite it. The
    `version_id` the record names is a digest over the contributing versions, so "one content
    identity per run record" (FR-017h) holds with more than one source endorsed.
    """
    if not versions:
        return EndorsedCorpus()

    documents: dict[str, EndorsedDocument] = {}
    for version in versions:
        documents.update(version.documents)

    ordered = sorted(versions, key=lambda version: version.version_id)
    if len(ordered) == 1:
        identity = ordered[0].version_id
    else:
        import hashlib

        digest = hashlib.sha256()
        for version in ordered:
            digest.update(version.version_id.encode())
            digest.update(b"\x00")
        identity = digest.hexdigest()

    # The OLDEST sync, not the newest: the age disclosure must describe the staleness a reader
    # could actually be affected by. Reporting the freshest of several sources would let one
    # recently-synced source vouch for the currency of material synced months ago.
    stamps = [version.synced_at for version in versions if version.synced_at is not None]

    return EndorsedCorpus(
        digest=identity,
        documents=documents,
        synced_at=min(stamps) if stamps else None,
        sources=frozenset(version.source for version in versions),
    )
