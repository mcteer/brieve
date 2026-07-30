# SPDX-License-Identifier: Apache-2.0
"""Provenance-at-read: what the agent consulted, as published at that moment.

ADR-0030 splits artifacts in two. What the agent **executes** is pinned — skills, prompts,
policies, models, pack code. What it **consults** is fetched fresh, because reference
guidance that was pinned would be stale guidance presented as current.

Fetching fresh creates the problem this module solves. If a run consulted a page and the page
later changed, an attestation reconstructed today would cite text the run never saw. So the
URL, the timestamp, and a **content hash** are archived with the run record at the moment of
reading, and the attestation cites *what was read* rather than what is current.

**The hash, not the content.** Guidance can be long, and the audit trail is append-only —
archiving text would make an unbounded external document permanently resident in evidence.
The hash answers the question an attestation actually asks: *was this the same text?* It is
computed under the run's own salt, like every other content hash in this platform, so two
runs reading identical guidance produce different digests and neither can be used to probe
the other's reading.

**Honest limit, and it is significant**: the corpus left with US6. Nothing in 013 gives an
agent real guidance to read, so this mechanism is proven against a controlled fixture. The
mechanism is built and the corpus is not — `contracts/conformance-packs.md` records the
difference, and a green run here is not evidence that consulting real guidance works.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from core.audit.chain import rfc3339_utc
from core.authority.hashing import content_hash
from core.telemetry.counters import record_retrieval


@dataclass(frozen=True)
class ConsultedArtifact:
    """One thing the agent read, and exactly what it said at the time.

    Frozen because a record that could be edited after the read is a record of what somebody
    later thought was read.
    """

    url: str
    #: When it was read. RFC 3339 UTC, matching the audit chain's own encoding, so an
    #: investigator is not comparing two timestamp formats across two records.
    read_at: str
    #: HMAC-SHA256 under the run's salt. Answers "was this the same text" without carrying
    #: the text, and without being comparable across runs.
    content_hash: str
    #: Which pack's guidance this was, when a pack prompted the lookup. Empty otherwise.
    pack: str = ""
    section: str = ""

    def as_payload(self) -> dict[str, str]:
        return {
            "url": self.url,
            "read_at": self.read_at,
            "content_hash": self.content_hash,
            "pack": self.pack,
            "section": self.section,
        }


class GuidanceSource(Protocol):
    """Where consulted guidance is fetched from.

    A seam because 013 has no corpus: the fixture implementation is what proves the
    mechanism, and the first real source arrives with the answering feature. A concrete
    fetcher here would have hard-coded an assumption about a corpus nobody has chosen.
    """

    def fetch(self, url: str) -> str:
        """Return the guidance text as published right now, or raise."""
        ...


class FixtureGuidance:
    """A controlled document, so the mechanism can be proven without a corpus.

    **Named a fixture rather than a source.** A class called `LocalGuidance` would read as a
    deployment option; this one cannot be mistaken for the real thing, which matters because
    the distinction between "the mechanism works" and "consulting real guidance works" is the
    honest limit recorded in the conformance contract.
    """

    def __init__(self, documents: Mapping[str, str]) -> None:
        self._documents = dict(documents)

    def fetch(self, url: str) -> str:
        if url not in self._documents:
            # Fresh sometimes means absent — the edge case the spec names. An unreachable
            # consulted artifact must refuse rather than resolve to empty: a run that
            # "consulted" nothing and recorded a hash of nothing would be attesting to a
            # reading that never happened.
            raise GuidanceUnavailable(f"no guidance at {url}")
        return self._documents[url]

    def set(self, url: str, text: str) -> None:
        """Change the document, so a row can prove the record does not follow it."""
        self._documents[url] = text


class GuidanceUnavailable(Exception):
    """Consulted guidance could not be fetched. Never resolved to empty."""


def consult(
    url: str,
    *,
    source: GuidanceSource,
    run_salt: bytes,
    pack: str = "",
    section: str = "",
    now: datetime | None = None,
) -> tuple[str, ConsultedArtifact]:
    """Read guidance and produce the record of having read it.

    Returns both, deliberately. The caller needs the text to reason with and the record to
    archive, and a function that returned only the text would leave archiving to whoever
    remembered — which is how provenance-at-read becomes provenance-at-read-usually.
    """
    text = source.fetch(url)
    stamped = rfc3339_utc(now or datetime.now(UTC))
    record = ConsultedArtifact(
        url=url,
        read_at=stamped,
        content_hash=content_hash(run_salt, text),
        pack=pack,
        section=section,
    )
    # The backlog counter (ADR-0031): what was looked up, how often. The target only —
    # never what it said.
    record_retrieval(url, pack=pack, section=section)
    return text, record


def archive(record: ConsultedArtifact, run_record: dict[str, Any]) -> dict[str, Any]:
    """Append a consulted-artifact record to a run record.

    Append-only within the run record for the same reason the trail is: an attestation that
    could lose a reading is an attestation that cannot say what the agent worked from.
    """
    consulted = list(run_record.get("consulted", []))
    consulted.append(record.as_payload())
    return {**run_record, "consulted": consulted}


__all__ = [
    "ConsultedArtifact",
    "FixtureGuidance",
    "GuidanceSource",
    "GuidanceUnavailable",
    "archive",
    "consult",
]
