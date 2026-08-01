# SPDX-License-Identifier: Apache-2.0
"""The pinned corpus, and what makes a citation resolvable.

**The manifest is the pin.** The corpus carries no version metadata anywhere — checked against the
source, not assumed — so change can only be detected by content. A digest is that, and it is a
stronger pin than a copy: a copy drifts from upstream silently, a digest mismatch is loud.

**Nothing is fetched here.** `infra/bin/corpus-sync` populates the cache; this reads it and refuses
what does not match. A corpus that fetched at answer time would make every answer depend on a third
party being reachable, and would make "pinned" untrue.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

DEFAULT_MANIFEST: Final[Path] = Path(__file__).resolve().parents[3] / "corpus" / "manifest.json"
DEFAULT_CACHE: Final[Path] = Path(__file__).resolve().parents[3] / ".corpus-cache"


class CorpusUnavailable(Exception):
    """The corpus is missing, or does not match its pin.

    **A refusal, never a fallback.** Answering from content that does not match the manifest would
    produce citations into a document nobody pinned, which is the failure this whole path exists to
    prevent — a citation that looks like evidence and is not.
    """


@dataclass(frozen=True)
class Document:
    path: str
    url: str
    digest: str
    anchors: frozenset[str]


@dataclass(frozen=True)
class Corpus:
    """What an answer may cite, and the identity of that content."""

    digest: str
    documents: dict[str, Document]

    def resolves(self, path: str, anchor: str) -> bool:
        """Whether a citation points at a section that exists.

        **The single most important check in this feature.** An unresolvable citation is worse than
        no citation: it reads as evidence, and a reader who follows it and finds nothing has been
        told something false about what this platform knows.
        """
        document = self.documents.get(path)
        return document is not None and anchor in document.anchors

    def url_for(self, path: str, anchor: str) -> str:
        return f"{self.documents[path].url}#{anchor}"


def load_corpus(
    *, manifest: Path = DEFAULT_MANIFEST, cache: Path = DEFAULT_CACHE, verify: bool = True
) -> Corpus:
    """Read the pin, and refuse a cache that does not match it."""
    if not manifest.exists():
        raise CorpusUnavailable(
            f"no corpus manifest at {manifest}; run `bash infra/bin/corpus-sync`"
        )
    data = json.loads(manifest.read_text())
    documents: dict[str, Document] = {}
    for entry in data["documents"]:
        path = str(entry["path"])
        if verify:
            cached = cache / (path.strip("/").replace("/", "__") + ".html")
            if not cached.exists():
                raise CorpusUnavailable(
                    f"{path} is pinned but not cached; run `bash infra/bin/corpus-sync`"
                )
            actual = hashlib.sha256(cached.read_bytes()).hexdigest()
            if actual != entry["digest"]:
                raise CorpusUnavailable(
                    f"{path} does not match its pin — the corpus changed, and every citation "
                    f"against it must be re-verified rather than trusted"
                )
        documents[path] = Document(
            path=path,
            url=str(entry["url"]),
            digest=str(entry["digest"]),
            anchors=frozenset(entry["anchors"]),
        )
    return Corpus(digest=str(data["corpus_digest"]), documents=documents)


__all__ = ["Corpus", "CorpusUnavailable", "Document", "load_corpus"]
