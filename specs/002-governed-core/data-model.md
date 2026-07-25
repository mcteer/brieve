# Data Model: Governed Core MVP

**Feature**: `specs/002-governed-core`
**Date**: 2026-07-24

Runtime entities for the in-process governed pipeline. Persistence is limited to an
append-only audit sink (in-memory in 002). No multi-tenant partition beyond single-run
isolation by correlation ID.

## Entities

### CorrelationId

| Field | Type | Rules |
| --- | --- | --- |
| value | `str` | Non-empty after strip; opaque to core (UUID recommended) |

**Validation**: Missing/blank at run start → refuse start (fail closed). Immutable for the
life of the run.

### GovernedRun

| Field | Type | Rules |
| --- | --- | --- |
| correlation_id | CorrelationId | Required; exactly one per run |
| scope | `frozenset[str]` | Declared tool-name allow-set; empty means deny-all tools |
| audit_sink | AuditSink | Required; receives append-only entries |
| registry | ToolRegistry | Required for invoke |
| hook_pipeline | HookPipeline / engine config | Governance-first registration |
| state | enum | `active` \| `refused` (start failed) \| (optional) `closed` |

**Relationships**: Owns the correlation ID; scopes tool invokes; all audit entries for the
run share `correlation_id`.

**State transitions**:

```text
(start requested) --missing correlation--> refused
(start requested) --valid--> active
active --invoke_tool*--> active   # multiple calls share one ID
```

### ToolRegistration

| Field | Type | Rules |
| --- | --- | --- |
| name | `str` | Non-empty; unique in registry |
| handler | callable | Invoked only after pre-hooks allow |
| metadata | map | Minimal; optional risk markers deferred |

**Validation**: Unknown name at resolve → deny (FR-004). Not in run.scope → deny (FR-005).

### HookRegistration

| Field | Type | Rules |
| --- | --- | --- |
| name | `str` | Identifier for probes/audit |
| phase | `pre` \| `post` | |
| capability_kind | `governance` \| `other` | Governance sorts before other |
| handler | callable | Return decision or raise |

### HookDecision

| Field | Type | Rules |
| --- | --- | --- |
| outcome | `allow` \| `deny` | Exceptions in enforcement path → treat as deny |
| reason_code | `str` | Stable code for FR-014 |
| message | `str` | Safe user-facing text; no secrets / entitlement dumps |
| phase | `pre` \| `post` | |
| hook_name | `str` | |
| correlation_id | CorrelationId | Copied from run |
| tool_name | `str` | |

### ToolInvocationRecord

| Field | Type | Rules |
| --- | --- | --- |
| correlation_id | CorrelationId | |
| tool_name | `str` | |
| arguments_ref | redacted metadata | Keys / hashes only — never raw secret values |
| executed | `bool` | True only if body ran |
| execution_error | optional safe code | No raw exception text with secrets |
| pre_decision | HookDecision summary | |
| post_decision | optional | Present when post ran |

### AuditEntry

| Field | Type | Rules |
| --- | --- | --- |
| correlation_id | CorrelationId | Join key |
| seq | `int` | Monotonic per run starting at 0; no gaps |
| event_type | enum/str | e.g. `run_start`, `pre_decision`, `tool_outcome`, `post_decision`, `enforcement_error` |
| timestamp | datetime | From injectable clock in tests |
| payload | redacted map | References/hashes/metadata only |
| prev_hash | hex str | Genesis sentinel: 64 ASCII `0` chars; else prior `entry_hash` |
| entry_hash | hex str | SHA-256 over canonical bytes of entry fields excluding `entry_hash` |

**Invariants**: Append-only; no in-place mutation API; chain verifiable; retrievable by
correlation ID in causal (`seq`) order (FR-008).

### AuditSink

| Operation | Semantics |
| --- | --- |
| `append(entry)` | Compute/validate hash link; store; reject mutations of past seq |
| `list_by_correlation_id(id)` | Causal order; complete chain for run |

**Implementations in 002**: `InMemoryAuditSink` only.

### Span observation (telemetry)

Not a persisted entity. Each hook decision emits an OTel span with attributes at least:
`correlation_id`, `tool_name`, `decision`, `phase`, `hook_name` / `capability_kind`.
No secret values in attributes.

### ScriptedAgent (test double)

| Field | Type | Rules |
| --- | --- | --- |
| calls | sequence of `(tool_name, arguments)` | Fixed; no model |

Emits invokes through `invoke_tool`; never calls live models (FR-013).

## Relationships

```text
GovernedRun 1--1 CorrelationId
GovernedRun 1--* AuditEntry          (via AuditSink, joined by correlation_id)
GovernedRun *--1 ToolRegistry
ToolRegistry 1--* ToolRegistration
GovernedRun --invokes--> ToolInvocationRecord
ToolInvocationRecord --produces--> HookDecision (pre/post)
HookDecision --emits--> OTel span
HookDecision --appends--> AuditEntry
ScriptedAgent --calls--> invoke_tool(GovernedRun, ...)
```

## Validation rules (cross-cutting)

1. No tool body execution without a prior pre allow from the pipeline (FR-001–FR-003).
2. Enforcement errors deny; never allow (FR-006).
3. Post-hooks run after tool-body failure (FR-015).
4. Secret values never appear in AuditEntry.payload, span attributes, or denial messages
   (FR-010, FR-014).
5. Hash chain: for all i>0, `entries[i].prev_hash == entries[i-1].entry_hash`, and
   recomputed `entry_hash` matches stored (FR-008).
