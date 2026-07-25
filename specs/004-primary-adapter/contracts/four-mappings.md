# Contract: Four adapter mappings

**Feature**: `specs/004-primary-adapter`
**Status**: Planned
**Depends on**: `specs/002-governed-core` (`invoke_tool`), `specs/003-per-task-authority`
(`start_governed_run`, authority bind)

## Purpose

Define the only permitted contents of the primary adapter (ADR-0001).

## Mappings (normative)

| # | Framework concept | Core / seam target | Invariant |
| --- | --- | --- | --- |
| 1 | Tools | `invoke_tool(run, tool_name, arguments)` | No tool-body execution outside this entry |
| 2 | State | `DurabilityProvider.save/load` | Checkpoints hold state, never credentials |
| 3 | Interrupts | `ApprovalHook.request_approval(...)` | Default deny; errors deny |
| 4 | Run context | identity + correlation + `agent_definition_id` into `start_governed_run` | Missing required inputs refuse start |

## Public adapter surface (logical)

```text
build_governed_agent(...) -> Agent
start_adapter_run(..., subject_user_id, agent_definition_id, requested_scope, identity_fabric, ...)
    -> AdapterRunContext  # binds GovernedRun or raises refuse
```

`start_adapter_run` MUST call `start_governed_run` with governance included
(`include_governance=True` or the default True with no override path). Exact Python
symbol names may refine at implement time; invariants MUST hold.

## Invariants

1. `src/core` never imports the agent framework.
2. Adapter modules contain no authority intersection, audit schema, or registry lifecycle
   logic beyond calling core APIs.
3. A framework tool call that core would deny never produces a successful side-effecting
   native execution.
4. Mapping (2) and (3) MAY be exercised with fakes; they MUST exist as call paths.
5. This contract does not authorize a second framework adapter.

## Related

- [governance-capability.md](./governance-capability.md)
- [data-model.md](../data-model.md)
