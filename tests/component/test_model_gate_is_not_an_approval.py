# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — a model verdict never satisfies a human approval (FR-015, SC-010).

**This establishes a distinction rather than repairing one.** `AuditEventType` has no
approval member at all — `core/approvals/types.py` is a Protocol and two doubles with no
event of its own (research.md F3). So the trail could not be made to distinguish a model
gate from a human approval by adding nuance to an existing pair, because the pair did not
exist.

Adding `MODEL_GATE` unilaterally means that when human approvals gain their own event, the
two are **already separate** rather than needing to be untangled. That is worth more than it
sounds: untangling a conflated record retroactively means deciding, for entries already
written, which kind each one was — and the information to decide is exactly what was lost.

The rule itself is Principle IX: a model verdict MAY gate a step and MUST NEVER satisfy an
approval requirement policy assigns to a human.
"""

from __future__ import annotations

from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink


def _gate(sink: InMemoryAuditSink, **payload: object) -> None:
    sink.append_event(
        correlation_id="corr-gate-001",
        tenant_id="tenant-1",
        event_type=AuditEventType.MODEL_GATE,
        payload={"run_id": "corr-gate-001", "role": "judge", "verdict": "pass", **payload},
    )


def test_a_model_gate_has_its_own_event_type() -> None:
    sink = InMemoryAuditSink()
    _gate(sink, model="anthropic/claude-opus@5", cell="vault:anthropic/claude-opus@5:judge")

    entries = sink.list_by_correlation_id("corr-gate-001")
    assert [e.event_type for e in entries] == [AuditEventType.MODEL_GATE]


def test_no_approval_event_exists_to_be_confused_with() -> None:
    """F3, asserted so the claim stays true rather than being remembered.

    If an approval event is added later, this row fails — and that is the moment to check
    that the two are still distinguishable, which is precisely when somebody should look.
    """
    members = {member.value for member in AuditEventType}
    approval_shaped = {m for m in members if "approv" in m}
    assert not approval_shaped, (
        f"an approval event now exists: {approval_shaped}. MODEL_GATE was added on the basis "
        f"that no such event existed; confirm the two are distinguishable and update this row"
    )


def test_a_model_gate_is_distinguishable_from_every_other_event() -> None:
    """Distinguishable by TYPE, not by reading a payload field.

    A verdict recorded as a generic event with `{"kind": "model"}` inside would be
    distinguishable only to a reader who knew to look, and an investigator filtering by event
    type would see it as whatever the outer type claimed.
    """
    assert AuditEventType.MODEL_GATE.value == "model_gate"
    assert AuditEventType.MODEL_GATE not in {
        AuditEventType.PRE_DECISION,
        AuditEventType.POST_DECISION,
        AuditEventType.TOOL_OUTCOME,
        AuditEventType.AUTHORITY_ISSUED,
    }


def test_a_gate_and_a_fallback_are_separate_events() -> None:
    """Two different questions, and an investigator asking the second must not filter the first.

    "A model decided something" and "the model that ran was not the model that was pinned"
    are unrelated concerns that happen to involve models. Conflating them means anyone
    looking for a substituted cell wades through every verdict the run produced.
    """
    sink = InMemoryAuditSink()
    _gate(sink, model="anthropic/claude-opus@5", cell="c")
    sink.append_event(
        correlation_id="corr-gate-001",
        tenant_id="tenant-1",
        event_type=AuditEventType.MATRIX_FALLBACK,
        payload={"run_id": "corr-gate-001", "role": "judge", "pinned_cell": "a", "used_cell": "b"},
    )

    types = [e.event_type for e in sink.list_by_correlation_id("corr-gate-001")]
    assert types == [AuditEventType.MODEL_GATE, AuditEventType.MATRIX_FALLBACK]
    assert len(set(types)) == 2, "a gate and a fallback collapsed into one event type"


def test_a_model_gate_is_inside_the_hash_chain() -> None:
    """A verdict outside the chain could be added or removed after the fact.

    The whole value of distinguishing a model gate from a human approval is that the
    distinction is *evidence*. Evidence that can be edited without breaking anything is a
    claim.
    """
    sink = InMemoryAuditSink()
    _gate(sink, model="m@1", cell="c")

    entry = sink.list_by_correlation_id("corr-gate-001")[0]
    assert entry.entry_hash
    assert entry.prev_hash == "0" * 64
    assert entry.tenant_id == "tenant-1", "the bounding dimension is not on the entry"
