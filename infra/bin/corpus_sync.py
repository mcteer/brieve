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

REPO = Path(__file__).resolve().parents[2]
CACHE = REPO / ".corpus-cache"
MANIFEST = REPO / "corpus" / "manifest.json"
BASE = "https://developer.hashicorp.com"
INDEXES = ("boundary", "nomad", "packer", "terraform", "vault")


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
    documents = []
    for path in _discover():
        try:
            html = _get(BASE + path)
        except Exception as exc:  # noqa: BLE001 — one unreachable document must not lose the rest
            print(f"  SKIP {path}: {type(exc).__name__}", file=sys.stderr)
            continue
        parser = _Sections()
        parser.feed(html)
        digest = hashlib.sha256(html.encode()).hexdigest()
        (CACHE / (path.strip("/").replace("/", "__") + ".html")).write_text(html)
        documents.append(
            {
                "path": path,
                "url": BASE + path,
                "digest": digest,
                "anchors": [s["anchor"] for s in parser.sections],
            }
        )
        print(f"  {path}  {len(parser.sections)} sections")
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
