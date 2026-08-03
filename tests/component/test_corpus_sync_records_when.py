# SPDX-License-Identifier: Apache-2.0
"""The sync records when it ran — and a failed sync records nothing at all.

Two halves of US2, driven against the real `main()` with only the network faked. The fixture
upstream is deliberately tiny: what these rows measure is the manifest's shape and the
write-or-don't decision, not the HTML parser 024 settled.

**The failure half is FR-007's component row.** The workflow's red run is the operator-facing
signal, but the property underneath it is that a refused fetch leaves the pin byte-identical —
a refresh that degraded the current ground while failing would be worse than no refresh.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _sync_module() -> Any:
    """`infra/bin/corpus_sync.py` — imported by path because `infra/bin` is not a package."""
    spec = importlib.util.spec_from_file_location(
        "corpus_sync_under_test", ROOT / "infra" / "bin" / "corpus_sync.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_INDEX = '<a href="/validated-patterns/vault/one-pattern">one</a>'
_PAGE = (
    "<html><body><main>"
    '<h2 id="first">First section</h2><p>Some pinned guidance.</p>'
    "</main></body></html>"
)


def _redirect_writes(module: Any, tmp_path: Path) -> None:
    module.CACHE = tmp_path / "cache"
    module.MANIFEST = tmp_path / "corpus" / "manifest.json"
    module.DOCS = tmp_path / "corpus" / "documents"


def _fixture_upstream(url: str) -> str:
    return (
        _INDEX
        if url.rstrip("/").endswith(tuple(f"/{i}" for i in ("vault",)))
        else (_INDEX if "/validated-patterns/" in url and url.count("/") <= 5 else _PAGE)
    )


def test_the_manifest_records_when_the_sync_ran(tmp_path: Path) -> None:
    module = _sync_module()
    _redirect_writes(module, tmp_path)
    module._get = _fixture_upstream

    before = datetime.now(UTC)
    assert module.main() == 0
    after = datetime.now(UTC)

    manifest = json.loads(module.MANIFEST.read_text())
    assert "synced_at" in manifest, "the sync wrote a pin that cannot say when it was made"
    recorded = datetime.fromisoformat(manifest["synced_at"])
    assert recorded.tzinfo is not None, "a naive timestamp is not comparable to anything"
    assert before <= recorded <= after


def test_an_unchanged_upstream_moves_the_timestamp_and_nothing_else(tmp_path: Path) -> None:
    """US2 scenario 2 — "we checked" is distinguishable from "we changed".

    This is the whole reason a no-change week still proposes a refresh: the diff IS the
    record that somebody looked.
    """
    module = _sync_module()
    _redirect_writes(module, tmp_path)
    module._get = _fixture_upstream

    assert module.main() == 0
    first = json.loads(module.MANIFEST.read_text())
    assert module.main() == 0
    second = json.loads(module.MANIFEST.read_text())

    assert first["corpus_digest"] == second["corpus_digest"], "unchanged content changed digest"
    assert first["documents"] == second["documents"]
    assert second["synced_at"] >= first["synced_at"]
    moved = {k for k in second if second[k] != first.get(k)}
    assert moved <= {"synced_at"}, f"a no-change sync moved more than the timestamp: {moved}"


def test_a_refused_upstream_writes_nothing(tmp_path: Path) -> None:
    """FR-007's component half: the pin survives a failed refresh byte-identical."""
    module = _sync_module()
    _redirect_writes(module, tmp_path)
    module._get = _fixture_upstream
    assert module.main() == 0

    before = module.MANIFEST.read_bytes()
    documents_before = {p.name: p.read_bytes() for p in sorted(module.DOCS.iterdir())}

    def _unreachable(url: str) -> str:
        raise OSError("upstream is unreachable")

    module._get = _unreachable
    with pytest.raises(OSError):
        module.main()

    assert module.MANIFEST.read_bytes() == before, "a failed sync rewrote the pin"
    assert {p.name: p.read_bytes() for p in sorted(module.DOCS.iterdir())} == documents_before
