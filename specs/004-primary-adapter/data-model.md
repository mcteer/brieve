# Data Model: Primary Adapter

**Feature**: `specs/004-primary-adapter`
**Date**: 2026-07-25

## Entities

### AdapterRunContext (deps)

Framework run-context / deps object carried on adapter-started agent runs.

| Field | Type | Rules |
| --- | --- | --- |
| `governed_run` | `GovernedRun` | Bound after successful start; required before any tool mapping call |
| `correlation_id` | `str` | Same ID as `governed_run.correlation_id`; non-empty |
| `subject_user_id` | `str` | Requesting human; required at start |
| `agent_definition_id` | `str` | Non-empty; keys ceiling/policy resolution in fabric fakes |
| `approval_hook` | `ApprovalHook` | Thin interrupt target; default deny-closed in tests unless injected |
| `durability` | `DurabilityProvider` | Thin state seam; default in-memory |

**Validation**: Missing `governed_run`, blank correlation ID, blank subject, or blank
`agent_definition_id` → refuse start / deny tool mapping (fail closed).

**Relationships**: Created by adapter start helper; consumed by toolset mapping and
GovernanceCapability hooks.

### GovernanceCapability

Framework capability object implementing governance composition for the primary adapter.

| Property | Rules |
| --- | --- |
| Kind | Always treated as governance; builder prepends it |
| Ordering | Observed before any co-resident non-governance capability on tool calls |
| Failure mode | Exception or missing run → deny (no tool body) |
| Contents | Glue only — delegates enforcement to core hooks via `invoke_tool` |

**Relationships**: Composed into the framework `Agent` alongside optional co-resident
capabilities used only for order probes in conformance.

### GovernedToolMapping

Logical entity: one framework-visible tool name bound to one registry tool.

| Field | Type | Rules |
| --- | --- | --- |
| `tool_name` | `str` | Must match `ToolRegistry` name |
| `call` | mapping fn | MUST call `invoke_tool(run, tool_name, arguments)` exactly once per attempt |

**Validation**: No parallel native handler path. Deny from core ⇒ failed tool outcome,
zero registry side effects beyond what core already prevented.

### CheckpointBlob (durability)

Opaque state payload for the thin durability seam.

| Field | Type | Rules |
| --- | --- | --- |
| `blob_id` | `str` | Opaque id |
| `payload` | `bytes` \| JSON-ish mapping | Framework state only |
| `correlation_id` | `str` | Join metadata; not authority |

**Validation**: MUST NOT contain credential secret values, `run_salt`, or brokered
material. Tests assert with `assert_no_secret_values` / structural absence checks.

**Relationships**: Written/read only through `DurabilityProvider`; adapter maps
framework state ↔ blob.

### DurabilityProvider (protocol)

| Method | Behavior |
| --- | --- |
| `save(blob)` | Persist checkpoint metadata + payload |
| `load(blob_id)` | Return blob or miss |
| Failure | Errors fail closed for the mapping call; no credential leak |

**004 default**: `InMemoryDurabilityProvider`. Full resume semantics out of scope.

### ApprovalHook (protocol)

| Method | Behavior |
| --- | --- |
| `request_approval(tool_name, arguments, correlation_id)` → allow \| deny | Default deny |
| Failure | Deny (fail closed) |

**Relationships**: Interrupt / approval-required framework surfaces call this; no UI.

### IdentityFabric (extension)

Existing 003 protocol gains definition-keyed ceiling resolution:

| Method | Change |
| --- | --- |
| `resolve_ceiling(agent_definition_id: str)` | Required parameter; fakes return per-definition ceilings |
| `resolve_policy(agent_definition_id: str)` | Required parameter; fakes may return a global policy while accepting the id |

**Validation**: Unknown definition id → unavailable / refuse (fail closed), never an
open ceiling.

### GovernedRun / TaskCredentialRef

Unchanged from 002/003 except that adapter-started runs populate them via
`start_governed_run(..., agent_definition_id=...)`. Adapter MUST NOT widen
`live_effective` or mint credentials itself.

## State transitions

```text
[inputs: user, definition, scope, fabric]
        │
        ▼
 start_adapter_run / start_governed_run
        │
        ├─ refuse ──► no GovernedRun; no agent tool mapping armed
        │
        ▼
 AdapterRunContext bound (ACTIVE run)
        │
        ▼
 framework tool call ──► invoke_tool
        │
        ├─ deny / error ──► failed tool outcome; zero side effects
        │
        └─ allow ──► one tool-body execution; audit+spans joined
```

Interrupt path (thin): framework approval-required → `ApprovalHook` → deny-by-default
unless test injects allow; still no tool body without subsequent successful
`invoke_tool`.

## Validation summary (normative)

1. Core has zero agent-framework imports after this feature.
2. Every adapter tool execution attempt enters `invoke_tool`.
3. GovernanceCapability is first among co-resident capabilities (conformance).
4. Checkpoint blobs never carry secrets / `run_salt` / brokered material.
5. Blank `agent_definition_id` cannot start a governed adapter run.
6. The core entities above — `DurabilityProvider`, `ApprovalHook`, and the `IdentityFabric`
   definition-keyed extension — are the **complete** set of sealed-core changes this
   feature makes (FR-016). A fourth core entity appearing in implementation is out of
   scope and needs its own spec.
