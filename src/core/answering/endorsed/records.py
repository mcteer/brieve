# SPDX-License-Identifier: Apache-2.0
"""What a synced version is, and the identity a run pins (045, T005).

Pure data and the digest arithmetic over it — no store, no fabric, no I/O. Split out so the
version identity can be computed and asserted without a database, which is what lets the
hermetic rows say something about the thing the live legs later exercise.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

#: The states a version passes through. A review-sync lands as `candidate` and changes nothing
#: about answers; adoption flips one to `adopted` and the previous one to `superseded`.
#: **Superseded is not deleted** — runs in flight pin it (research R3/R4).
CANDIDATE: Final[str] = "candidate"
ADOPTED: Final[str] = "adopted"
SUPERSEDED: Final[str] = "superseded"
VERSION_STATES: Final[frozenset[str]] = frozenset({CANDIDATE, ADOPTED, SUPERSEDED})


@dataclass(frozen=True)
class EndorsedDocument:
    """One citable document of a customer's own material.

    Deliberately the same shape as `answering.corpus.Document` without importing it: the two
    corpora satisfy one contract, and a shared base class would be the coupling research R1
    rejected — it is the seam through which a change made for customer content reaches the
    pinned reader.
    """

    path: str
    url: str
    digest: str
    anchors: frozenset[str]
    sections: dict[str, str] = field(default_factory=dict)

    def text_at(self, anchor: str) -> str:
        return self.sections.get(anchor, "")


@dataclass(frozen=True)
class SyncedVersion:
    """One sync of one endorsed source. Immutable once written.

    `version_id` is the content identity: a run pins it, the run record names it, and a resumed
    run re-reads at it rather than re-resolving to current.
    """

    version_id: str
    tenant_id: str
    source: str
    upstream_tip: str
    synced_at: datetime
    synced_by: str
    state: str
    documents: dict[str, EndorsedDocument] = field(default_factory=dict)


def compute_version_id(source: str, documents: dict[str, EndorsedDocument]) -> str:
    """The identity of a body of content — **derived from the content, never assigned**.

    The pinned corpus's own reasoning, one corpus over: a digest is a stronger pin than a
    counter because a counter can be reused for different content and a digest cannot. Two syncs
    that find the upstream unchanged produce the same identity, which is what makes "this run
    read exactly what that run read" checkable rather than asserted.

    The upstream tip is deliberately **not** an input. A repository can be force-pushed, and a
    tip that names different content than it did yesterday would silently change what a pinned
    version means. Content decides; the tip is only how drift is *noticed*.
    """
    digest = hashlib.sha256()
    digest.update(source.encode())
    for path in sorted(documents):
        document = documents[path]
        digest.update(b"\x00")
        digest.update(path.encode())
        digest.update(b"\x00")
        digest.update(document.digest.encode())
        for anchor in sorted(document.anchors):
            digest.update(b"\x01")
            digest.update(anchor.encode())
    return digest.hexdigest()


def digest_of_section(body: str) -> str:
    return hashlib.sha256(body.encode()).hexdigest()


def digest_of_document(sections: dict[str, str]) -> str:
    """A document's digest is over its sections, so a changed word changes the identity.

    Verified on read (`EndorsedCorpus` refuses a mismatch), which is the endorsed half of what
    `load_corpus(verify=True)` does — and it must exist here for the same reason: content that
    changed underneath a pin would make a citation resolve to something other than what was
    endorsed, while still looking exactly like evidence.
    """
    digest = hashlib.sha256()
    for anchor in sorted(sections):
        digest.update(anchor.encode())
        digest.update(b"\x00")
        digest.update(sections[anchor].encode())
        digest.update(b"\x00")
    return digest.hexdigest()
