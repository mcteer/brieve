# Contract: Audit sink and hash chain

**Feature**: `specs/002-governed-core`
**Audience**: Core implementers, future audit providers, evidence/compliance reviewers
**Stability**: Schema fields and hash-chain rules are sealed-core (FR-008). Storage
backends may vary behind `AuditSink`; 002 ships in-memory only.

## Interface (logical)

```text
protocol AuditSink:
  append(entry: AuditEntry) -> None
  list_by_correlation_id(correlation_id: str) -> Sequence[AuditEntry]  # causal order
```

No `update`, `delete`, or overwrite operation exists on the supported path.

## AuditEntry (minimum fields)

| Field | Requirement |
| --- | --- |
| correlation_id | Required; joins the run |
| seq | Monotonic integer per run; no gaps |
| event_type | Discriminator for run_start / pre_decision / tool_outcome / post_decision / enforcement_error (names exact at impl) |
| timestamp | Aware datetime preferred |
| payload | Redacted map — references, hashes, reason codes; **never** secret values |
| prev_hash | Hex digest; genesis sentinel documented in impl |
| entry_hash | Hex SHA-256 digest over the canonical encoding of the entry excluding `entry_hash`. Canonical encoding is pinned: UTF-8 JSON with lexicographically sorted keys, no insignificant whitespace, timestamps as RFC 3339 UTC strings, `prev_hash` included. Two independent implementations MUST compute identical digests for the same entry. |

## Hash-chain rules

1. Genesis entry: `prev_hash` is exactly 64 ASCII `0` characters; `seq` is `0`.
2. For every subsequent entry: `prev_hash == prior.entry_hash`.
3. Recomputing `entry_hash` from stored fields MUST match the stored digest.
4. `list_by_correlation_id` returns entries sorted by `seq` ascending with no gaps.
5. Append MUST reject an entry that would break the chain (fail closed for that append).

## Correlation join

Every audit entry for a run carries that run's correlation ID. Investigators retrieve the
full trail with `list_by_correlation_id` (FR-007, FR-008, SC-003).

## Redaction

Payloads MUST NOT contain raw tool argument values or raw exception text that may embed
secrets. Prefer argument key lists, content hashes, and stable error codes (FR-010).
Argument content hashes are currently unsalted SHA-256 — acceptable while no real
secret-class arguments flow. Before identity and real product tools land (003+),
hashing moves to a per-run random salt (not a standing key, which Principle IV
forbids) so low-entropy values cannot be dictionary-recovered from audit records.

## 002 implementation

- `InMemoryAuditSink` in `src/core/audit/`
- Test access via `capture_audit` in `tests/harness`
- No SIEM export, no governed multi-tenant read path (ADR-0035 deferred)

## Related

- [../spec.md](../spec.md) — FR-007, FR-008, FR-010
- [harness-helpers.md](./harness-helpers.md) — `assert_audit_chain`, `assert_correlated`
- ADR-0009
