# Quickstart: validating audit egress

**Feature**: `specs/015-audit-egress` | **Date**: 2026-07-30

## Prerequisites

```bash
make dev-up && make dev-status   # brings up the collector store alongside the enclave
```

## 1 — The gap is real *(runs today, before implementation)*

```bash
# Both integrity mechanisms live in the same store as the data they guard:
grep -n "audit_stream_heads" src/core/audit/evidence_schema.sql
# Nothing ships anywhere — no destination, no shipper:
grep -rn "AuditDestination\|shipped_entries" src/ | wc -l    # -> 0
# And the platform's own DB credential can rewrite entries AND head, consistently.
```

## 2 — Everything ships *(after implementation)*

```bash
uv run --extra adapters --extra surfaces --extra portal pytest \
  tests/conformance/evidence -m host_enclave -q
```

**Expect**: entries and head observations at the collector store, byte-identical chain
fields, chain verifying on the second copy alone. See
[contracts/conformance-egress.md](contracts/conformance-egress.md) for the full row list.

## 3 — The attack that used to be invisible

Rewrite a local entry and lower the local head as the platform's database administrator — the
consistent rewrite that defeats the chain, the grant, and the head together. **Expect**:
reconciliation reports `entry_mismatch` / `local_truncated`, naming stream and sequence,
because the shipped head observations are the platform's own earlier claims and cannot be
un-claimed with the platform's credentials.

## 4 — The probe, not the assertion

```bash
# As the platform, attempt UPDATE and DELETE at the destination. Both must be refused.
# Point the same probe at a writable store: posture -> non_compliant, naming why.
```

**Expect**: `verified` only ever follows a refused tamper attempt (FR-020); a destination
that cannot be probed reports `unverified` and never claims protection.

## 5 — Outage honesty

Stop the collector container mid-run. **Expect**: runs continue (FR-014a — delivery never
gates the platform), the backlog observable rises (FR-016), and on restart every entry
written during the outage arrives with none lost (SC-009a). Then break local capture itself:
the step is refused (SC-009b) — the line clarify Q1 drew, demonstrated from both sides.

## 6 — Reconciliation is itself evidence

```bash
# Every reconcile pass — scheduled or on-demand — lands in the trail:
#   AUDIT_RECONCILED, with basis, caller, findings, backlog, posture.
# An unauthorized on-demand attempt is refused, and the refusal is recorded.
```

## What a passing run does NOT prove

- **The lag window is closed** — it is bounded and observable, not closed (research F4).
- **Administrators are actually different people** — the enclave proves credential
  separation; organizational separation is a deployment property.
- **Which copy is honest when they disagree** — divergence detection, not adjudication.
