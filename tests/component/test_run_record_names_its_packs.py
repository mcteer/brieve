# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — the run record names the content it executed (FR-020, T019b).

**FR-020's pinning held per-load, not per-run, until this.** A run resumed in a new
allocation reloads `packs/` from disk and verifies digests against the manifest *sitting
beside the content* — so content edited along with its manifest verifies clean, and the run
continues at a different skill version with nothing recording that anything changed.

`content_pins` on `RUN_START` is the fix: what this run loaded, by digest, in the trail. A
resumed run's content can then be compared to what the original run actually executed,
rather than to whatever is on disk now — the same move FR-021 makes for consulted guidance.

**The core records these without interpreting them.** Opaque name→digest pairs; nothing in
`core` learns what a pack is, and the product-blindness row keeps holding.
"""

from __future__ import annotations

from pathlib import Path

from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink
from core.authority.types import AuthorityScope
from core.run import start_governed_run
from surfaces.toolset import build_registry, content_pins
from tests.harness.fake_identity_fabric import fake_identity_fabric

PACKS_ROOT = Path(__file__).resolve().parents[2] / "packs"


def _start(pins: dict[str, str] | None) -> InMemoryAuditSink:
    sink = InMemoryAuditSink()
    start_governed_run(
        correlation_id="corr-pins-001",
        subject_user_id="user-1",
        agent_definition_id="applier",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"}), product_actions=frozenset()),
        identity_fabric=fake_identity_fabric(subject_user_id="user-1", tool_names={"echo"}),
        registry=build_registry()[0],
        audit_sink=sink,
        content_pins=pins,
    )
    return sink


def _run_start_payload(sink: InMemoryAuditSink) -> dict[str, object]:
    starts = [
        e
        for e in sink.list_by_correlation_id("corr-pins-001")
        if e.event_type == AuditEventType.RUN_START
    ]
    assert len(starts) == 1
    return starts[0].payload


def test_the_run_record_names_each_loaded_pack_and_digest() -> None:
    _, loaded = build_registry(packs=["vault"], packs_root=PACKS_ROOT)
    pins = content_pins(loaded)

    payload = _run_start_payload(_start(pins))

    recorded = payload.get("content_pins")
    assert isinstance(recorded, dict), "RUN_START carries no content_pins"
    assert "vault@0.1.0" in recorded
    assert "vault/vault-secret-access" in recorded
    assert recorded["vault/vault-secret-access"] == loaded["vault"].manifest.skills[0].digest


def test_changed_content_is_distinguishable_from_unchanged() -> None:
    """The property that makes the record worth having.

    Two runs whose loaded content differs produce different pins — so a resume whose pack
    content drifted is *detectable* from the trail, which per-load verification alone can
    never show.
    """
    _, loaded = build_registry(packs=["vault"], packs_root=PACKS_ROOT)
    original = content_pins(loaded)
    drifted = {**original, "vault/vault-secret-access": "0" * 64}

    assert original != drifted
    first = _run_start_payload(_start(original))
    second = _run_start_payload(_start(drifted))
    assert first["content_pins"] != second["content_pins"]


def test_a_run_loading_no_packs_carries_no_pins_field() -> None:
    """Absent, not empty. Every pre-013 run's RUN_START payload is unchanged —
    `{"scope": [...]}` exactly as 002 wrote it, so no snapshot or reader moves."""
    payload = _run_start_payload(_start(None))
    assert "content_pins" not in payload
    assert set(payload) == {"scope"}


def test_the_pins_are_inside_the_hash_chain() -> None:
    """A pin outside the chain could be edited after the fact, which is no pin at all."""
    _, loaded = build_registry(packs=["vault"], packs_root=PACKS_ROOT)
    sink = _start(content_pins(loaded))

    entries = sink.list_by_correlation_id("corr-pins-001")
    from core.audit.chain import verify_chain

    verify_chain(entries)  # raises if any entry, including RUN_START, was altered
