# Contract: GovernanceCapability (primary adapter)

**Feature**: `specs/004-primary-adapter`
**Status**: Planned
**Depends on**: ADR-0019, `specs/002-governed-core` hook ordering,
`contracts/four-mappings.md`

## Purpose

Pin governance-first composition and fail-closed behavior on the primary adapter path.

## Builder rules

1. `build_governed_agent` ALWAYS installs GovernanceCapability in the first capability
   position among co-resident capabilities.
2. Callers MAY pass additional capabilities; the builder prepends governance (or rejects
   configurations that would place non-governance first — implementer’s choice, but the
   observable order MUST be governance-first).
3. GovernanceCapability contributes only glue: lifecycle/tool interception that ends in
   `invoke_tool` / start-time core calls. It MUST NOT reimplement core hook algebra.
4. Governance is **terminal at the toolset layer** — its wrapper routes execution to
   `invoke_tool` rather than delegating inward, so no capability downstream can produce
   an ungoverned execution. A consequence: a co-resident capability's toolset wrapper is
   unreachable. `build_governed_agent` MUST **reject** such a configuration rather than
   install it, because a capability that appears active while doing nothing is the
   silent-pass failure ADR-0047 exists to prevent. The refusal names the capability and
   points at the supported alternative. GovernanceCapability is exempt from this rule —
   its wrapper is the terminal one. Observation of governed tool calls is available
   through the per-call hook chain, which runs around the governed call and is unaffected.

## Runtime rules

1. On each framework tool call reaching the mapping, core pre-hooks run with the full
   built-in governance set required by 003 (`authority`, `mirroring`, `governance`).
2. If GovernanceCapability or the tool mapping raises before/during delegation, the
   outcome is deny — never allow.
3. If `AdapterRunContext.governed_run` is missing or not ACTIVE, deny.
4. Co-resident probe capabilities used in tests MUST be observable after governance on
   the allow path (order log / span / probe_log).

## Reason / outcome surface

| Situation | Outcome |
| --- | --- |
| Core deny (`authority_*`, `unregistered`, …) | Failed tool outcome; zero side effects |
| Mapping / capability internal error | Deny / failed tool; audited as enforcement error when core path reached |
| Missing run / identity / definition at start | Refuse start |

Externally visible reason-code collapse under multi-tenancy remains a future tightening
(see 002/003 watch notes); conformance asserts deny + zero executions, not stable
external string taxonomies beyond what core already returns.

## Invariants

1. Governance-first order is conformance-asserted (see
   [conformance-adapter.md](./conformance-adapter.md)).
2. Fail-closed is conformance-asserted with an injected fault case.
3. Hook-context exposure rules from 002 still apply inside core; the adapter MUST NOT
   widen third-party hook context by smuggling `run` into `capability_kind=other` hooks.

## Related

- [four-mappings.md](./four-mappings.md)
- [conformance-adapter.md](./conformance-adapter.md)
