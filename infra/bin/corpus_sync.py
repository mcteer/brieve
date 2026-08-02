# SPDX-License-Identifier: Apache-2.0
"""Fetch the guidance corpus, extract sections, and pin it by content digest."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Final

REPO = Path(__file__).resolve().parents[2]
CACHE = REPO / ".corpus-cache"
MANIFEST = REPO / "corpus" / "manifest.json"
DOCS = REPO / "corpus" / "documents"
BASE = "https://developer.hashicorp.com"
INDEXES = ("boundary", "nomad", "packer", "terraform", "vault")


#: Credential-shaped strings that appear in IDENTITY documentation and must not be vendored.
#:
#: **Vendoring somebody else's docs imports whatever those docs illustrate**, and an
#: identity-integration guide illustrates tokens. The Backstage/Okta pattern prints an example JWT;
#: it is truncated upstream and is not a live credential, and the repository's rule still covers it
#: — plausible-looking fake ones count, precisely so that nobody has to adjudicate which is which.
#:
#: **Redacted here rather than allowlisted in the scanner.** A `.gitleaks.toml` entry for `corpus/`
#: would stop the scan looking at a directory that grows by re-running this script against a third
#: party — turning off the check exactly where the untrusted input arrives.
#:
#: Targeted rather than an entropy sweep: a JWT has an unmistakable shape, while "long
#: high-entropy run" also describes digests, resource ids and base64 diagrams that carry meaning.
CREDENTIAL_SHAPES: Final[tuple[re.Pattern[str], ...]] = (
    # JWT: base64url of a JSON header, which always begins `{"` → `eyJ`.
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+){0,2}"),
    # Vault/Nomad style tokens, and AWS access key ids.
    re.compile(r"\b(?:hv[sb]\.[A-Za-z0-9_-]{15,}|AKIA[0-9A-Z]{16})\b"),
)

REDACTED: Final[str] = "[redacted-by-corpus-sync]"


def redact(text: str) -> str:
    """Strip credential-shaped strings from vendored prose.

    The surrounding sentence is kept: *"the following is an example Backstage log that contains a
    JWT"* is the part an answer would cite, and the token itself carries no meaning a reader needs.
    """
    for pattern in CREDENTIAL_SHAPES:
        text = pattern.sub(REDACTED, text)
    return text


class _Content(HTMLParser):
    """Section text, keyed by the anchor a citation resolves to.

    Extracted rather than stored as raw markup: 33 pages of HTML is fourteen megabytes of
    navigation and script tags, and none of it is what an answer cites. What a citation points at
    is a section, so a section is what gets vendored.
    """

    _SKIP = {"script", "style", "nav", "header", "footer", "svg", "button"}

    def __init__(self) -> None:
        super().__init__()
        self.sections: list[dict[str, str]] = []
        self._in_main = 0
        self._skip = 0
        self._heading: str | None = None
        self._anchor: str | None = None
        self._buf: list[str] = []
        self._body: list[str] = []

    def _flush(self) -> None:
        if self._anchor and self._heading:
            text = " ".join(" ".join(self._body).split())
            self.sections.append(
                {"anchor": self._anchor, "title": self._heading, "text": redact(text)[:4000]}
            )
        self._anchor = self._heading = None
        self._body = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "main":
            self._in_main += 1
            return
        if tag in self._SKIP:
            self._skip += 1
            return
        if self._in_main and tag in {"h1", "h2", "h3"}:
            self._flush()
            self._anchor = dict(attrs).get("id")
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self._flush()
            self._in_main = max(0, self._in_main - 1)
            return
        if tag in self._SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if tag in {"h1", "h2", "h3"} and self._anchor is not None and self._heading is None:
            self._heading = " ".join("".join(self._buf).split())

    def handle_data(self, data: str) -> None:
        if self._skip or not self._in_main:
            return
        if self._anchor is not None and self._heading is None:
            self._buf.append(data)
        elif self._heading is not None:
            self._body.append(data)


class _Sections(HTMLParser):
    """Headings and their ids — the anchors a citation resolves to.

    **Only headings inside `<main>` count.** A first version took every `h1`–`h3` on the page and
    picked up `sidebar-label` from all 33 documents — navigation chrome, which would have let a
    citation "resolve" to a nav element and read as evidence. Caught by noticing one anchor in
    every single document.

    The filter is structural rather than a list of names to exclude. A denylist would have to
    anticipate every piece of chrome the site ever adds, and this repository has already been bitten
    twice in two days by a denylist that did not know about something.
    """

    def __init__(self) -> None:
        super().__init__()
        self.sections: list[dict[str, str]] = []
        self._id: str | None = None
        self._depth = 0
        self._buf: list[str] = []
        self._in_main = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "main":
            self._in_main += 1
            return
        if self._in_main and tag in {"h1", "h2", "h3"}:
            self._id = dict(attrs).get("id")
            self._depth = 1
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self._in_main = max(0, self._in_main - 1)
            return
        if tag in {"h1", "h2", "h3"} and self._depth:
            text = " ".join("".join(self._buf).split())
            if self._id and text:
                self.sections.append({"anchor": self._id, "title": text})
            self._depth = 0

    def handle_data(self, data: str) -> None:
        if self._depth:
            self._buf.append(data)


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "brieve-corpus-sync"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return str(r.read().decode("utf-8", "replace"))


def _discover() -> list[str]:
    paths: set[str] = set()
    for index in INDEXES:
        html = _get(f"{BASE}/validated-patterns/{index}")
        paths.update(re.findall(rf"/validated-patterns/{index}/[a-z0-9\-]+", html))
    return sorted(paths)


def main() -> int:
    CACHE.mkdir(exist_ok=True)
    MANIFEST.parent.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    documents = []
    for path in _discover():
        try:
            html = _get(BASE + path)
        except Exception as exc:  # noqa: BLE001 — one unreachable document must not lose the rest
            print(f"  SKIP {path}: {type(exc).__name__}", file=sys.stderr)
            continue
        parser = _Content()
        parser.feed(html)
        sections = [s for s in parser.sections if s["anchor"] and s["title"]]
        digest = hashlib.sha256(html.encode()).hexdigest()
        name = path.strip("/").replace("/", "__")
        (CACHE / (name + ".html")).write_text(html)
        # VENDORED, as sections rather than markup. See corpus/PROVENANCE.md.
        (DOCS / (name + ".json")).write_text(
            json.dumps({"path": path, "url": BASE + path, "sections": sections}, indent=2) + "\n"
        )
        documents.append(
            {
                "path": path,
                "url": BASE + path,
                "digest": digest,
                "anchors": [s["anchor"] for s in sections],
            }
        )
        print(f"  {path}  {len(sections)} sections")
    corpus_digest = hashlib.sha256("".join(d["digest"] for d in documents).encode()).hexdigest()
    MANIFEST.write_text(
        json.dumps(
            {
                "corpus_digest": corpus_digest,
                "document_count": len(documents),
                "documents": documents,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\n{len(documents)} documents, corpus digest {corpus_digest[:16]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
