# SPDX-License-Identifier: Apache-2.0
"""Public governance assertion helpers (semver seam)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from core.audit.chain import verify_chain
from core.audit.schema import AuditEntry
from core.audit.sink import InMemoryAuditSink
from core.authority.types import AuthorityScope, TaskCredentialRef
from core.tools.invoke import InvokeResult
from tests.harness.secrets import SECRET_MARKERS


def assert_denied_closed(result: InvokeResult, reason: str | None = None) -> None:
    """Assert deny / fail-closed outcome (not a soft skip)."""
    assert result.decision == "deny", f"expected deny, got {result.decision}"
    assert result.allowed is False, "expected allowed=False on deny"
    if reason is not None:
        assert result.reason_code == reason, (
            f"expected reason {reason!r}, got {result.reason_code!r}"
        )


def assert_correlated(
    audit: InMemoryAuditSink | Sequence[AuditEntry],
    spans: Sequence[Any],
    run_id: str,
) -> None:
    """Assert one correlation ID joins audit entries and hook-decision spans."""
    entries = (
        audit.list_by_correlation_id(run_id)
        if isinstance(audit, InMemoryAuditSink)
        else list(audit)
    )
    assert entries, "expected non-empty audit trail"
    for entry in entries:
        assert entry.correlation_id == run_id
    for span in spans:
        attrs = getattr(span, "attributes", None) or {}
        assert attrs.get("correlation_id") == run_id, f"span missing correlation_id={run_id}"


def assert_audit_chain(audit: InMemoryAuditSink | Sequence[AuditEntry]) -> None:
    """Assert append-only hash chain is intact with no gaps."""
    if isinstance(audit, InMemoryAuditSink):
        ids = audit.correlation_ids()
        assert ids, "expected audit entries"
        for cid in ids:
            verify_chain(audit.list_by_correlation_id(cid))
    else:
        verify_chain(list(audit))


def assert_no_secret_values(
    audit: InMemoryAuditSink | Sequence[AuditEntry] | Any,
    spans: Sequence[Any] | None = None,
    model_context: Any = None,
) -> None:
    """Assert fixture secret markers are absent from audit, spans, and model context."""
    blobs: list[str] = []
    if isinstance(audit, InMemoryAuditSink):
        for entry in audit.all_entries():
            blobs.append(entry.model_dump_json())
    elif isinstance(audit, Sequence):
        for entry in audit:
            if isinstance(entry, AuditEntry):
                blobs.append(entry.model_dump_json())
            else:
                blobs.append(str(entry))
    else:
        blobs.append(str(audit))

    if spans:
        for span in spans:
            attrs = getattr(span, "attributes", None) or {}
            blobs.append(str(dict(attrs)))
    if model_context is not None:
        blobs.append(str(model_context))

    combined = "\n".join(blobs)
    for marker in SECRET_MARKERS:
        assert marker not in combined, f"secret marker leaked: {marker}"


def assert_no_side_effect(target: Any) -> None:
    """Assert zero executions against a counter-bearing fake or handler."""
    if hasattr(target, "call_count"):
        assert target.call_count == 0, f"expected 0 calls, got {target.call_count}"
        return
    if hasattr(target, "executions"):
        assert target.executions == 0, f"expected 0 executions, got {target.executions}"
        return
    raise TypeError("target must expose call_count or executions")


def assert_scope_narrowed(token: TaskCredentialRef, *, at_most: AuthorityScope) -> None:
    """Assert issued effective authority is a subset of the user (or other) bound."""
    assert token.effective.tool_names <= at_most.tool_names, (
        f"tool_names amplified: {token.effective.tool_names!r} not ⊆ {at_most.tool_names!r}"
    )
    assert token.effective.product_actions <= at_most.product_actions, (
        f"product_actions amplified: {token.effective.product_actions!r} "
        f"not ⊆ {at_most.product_actions!r}"
    )


def assert_hook_order(observed: Sequence[str]) -> None:
    """Assert governance appears before other within each phase.

    Accepts bare kinds (``governance`` / ``other``) for a single phase, or
    ``phase:kind`` tokens for a full call probe log.
    """
    if observed and ":" in observed[0]:
        phases: dict[str, list[str]] = {}
        for item in observed:
            phase, kind = item.split(":", 1)
            phases.setdefault(phase, []).append(kind)
        for kinds in phases.values():
            _assert_gov_before_other(kinds)
        return
    _assert_gov_before_other(list(observed))


def _assert_gov_before_other(kinds: Sequence[str]) -> None:
    seen_other = False
    for kind in kinds:
        if kind == "other":
            seen_other = True
        elif kind == "governance":
            assert not seen_other, "governance hook observed after other"
        else:
            raise AssertionError(f"unexpected capability kind: {kind}")


def collect_span_attributes(spans: Iterable[Any]) -> list[dict[str, Any]]:
    return [dict(getattr(s, "attributes", None) or {}) for s in spans]
