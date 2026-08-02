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

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

DEFAULT_MANIFEST: Final[Path] = Path(__file__).resolve().parents[3] / "corpus" / "manifest.json"
DEFAULT_DOCUMENTS: Final[Path] = Path(__file__).resolve().parents[3] / "corpus" / "documents"


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
    #: SHA-256 of the UPSTREAM page. Detects that HashiCorp changed the document — which is the
    #: only way to detect it, since the corpus carries no version metadata anywhere.
    digest: str
    anchors: frozenset[str]
    sections: dict[str, str] = field(default_factory=dict)

    def text_at(self, anchor: str) -> str:
        return self.sections.get(anchor, "")


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
    *,
    manifest: Path = DEFAULT_MANIFEST,
    documents_dir: Path = DEFAULT_DOCUMENTS,
    verify: bool = True,
) -> Corpus:
    """Read the pin and the vendored sections, and refuse what does not line up.

    **Two different questions, kept separate.** The manifest's per-document digest is of the
    *upstream page* and answers "did HashiCorp change this" — the only way to ask, since the corpus
    carries no version metadata. `verify` here answers the narrower one: does every anchor the pin
    names actually exist in the content committed beside it. A citation resolving against a pin
    whose content is absent would be a citation to nothing.
    """
    if not manifest.exists():
        raise CorpusUnavailable(
            f"no corpus manifest at {manifest}; run `bash infra/bin/corpus-sync`"
        )
    data = json.loads(manifest.read_text())
    documents: dict[str, Document] = {}
    for entry in data["documents"]:
        path = str(entry["path"])
        sections: dict[str, str] = {}
        vendored = documents_dir / (path.strip("/").replace("/", "__") + ".json")
        if verify:
            if not vendored.exists():
                raise CorpusUnavailable(
                    f"{path} is pinned but its content is not vendored; run "
                    f"`bash infra/bin/corpus-sync`"
                )
            body = json.loads(vendored.read_text())
            sections = {str(s["anchor"]): str(s.get("text", "")) for s in body["sections"]}
            missing = set(entry["anchors"]) - set(sections)
            if missing:
                raise CorpusUnavailable(
                    f"{path} is pinned with anchors that its vendored content does not contain "
                    f"({sorted(missing)[:3]}) — a citation resolving against this would point at "
                    f"nothing"
                )
        documents[path] = Document(
            path=path,
            url=str(entry["url"]),
            digest=str(entry["digest"]),
            anchors=frozenset(entry["anchors"]),
            sections=sections,
        )
    return Corpus(digest=str(data["corpus_digest"]), documents=documents)


__all__ = ["Corpus", "CorpusUnavailable", "Document", "load_corpus"]
