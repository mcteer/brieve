# Contract: the harness ceiling record

**Feature**: `specs/010-identity-fabric`
**Status**: Planned
**Requires**: an ADR (FR-020) — this changes what the trust fabric holds

## Why a separate record rather than a registration field

The clarified answer was "a first-class field on the agent definition". Vault's
`agent_registry` engine has a closed schema (research Finding 3), so there is no field to
add. The substance of the clarification survives intact:

- authored **directly in the core's vocabulary** — tool names and product actions, not paths;
- read **directly**, with no translation step to get wrong;
- **disjoint** from the credential-issuance policy, which is what ADR-0044 requires.

What changes is only that it is its own record rather than a field on another one — which is
arguably a truer expression of "disjoint jurisdictions" than sharing a struct would have been.

## Location and shape

```
<mount>/harness-ceilings/<agent_definition_id>
  { "schema_version": 1,
    "tool_names": ["plan", "apply"],
    "product_actions": ["product.workspace.read"] }

<mount>/role-bindings/<role>
  { "schema_version": 1,
    "tool_names": [...], "product_actions": [...] }
```

Written by the same Terraform that writes the registration, so a definition and its ceiling
land in one apply. Two applies would mean a window in which a registered agent has no
ceiling — and per FR-005 that refuses, so the window is fail-closed rather than open. Stated
because "fail-closed" and "harmless" are different, and this one would look like an outage.

## Who may read it

A **narrow read policy** granting exactly these two prefixes, attached to a role for whoever
resolves identity. Not merged into `harness-database`: that policy exists so a run can write
its own record, and merging would mean anything able to reach the database could also read
every ceiling in the estate. The evidence path made the same separation for the same reason.

## Who may write it

**Terraform, from reviewed HCL — and nothing at runtime.** ADR-0015's division of labor is
the governance story: definitions in HCL (design-time, version-controlled, reviewed),
enforcement in Vault. A ceiling record change is therefore a pull request, with the same
review a registration change gets — which matters because **writing a wider ceiling record
is widening a scope**, and widening a scope is precisely the deliberate, reviewable act
ADR-0016 exists to govern. The HCL review path is that governance for design-time records,
the same way it already is for the registration's `ceiling_policies`.

Stated because it was the one governance question this feature's artifacts left implicit:
the read policy below is explicit about who may look, and a contract explicit about reads
and silent about writes invites the assumption that writes are somebody's runtime API. They
are not. No path in the harness, the MCP service, or any surface writes these records, and
the conformance lane asserts the reader role holds read capability only.

## Who may NOT read it

**No agent-governed tool** (FR-016). ADR-0015 puts the trust fabric structurally outside every
agent ceiling, and a tool able to ask what a ceiling is has taken a step toward changing one.
The row for this asserts the negative: with an agent's own credential, the ceiling paths are
denied by Vault — refused by the trust fabric, not by our code.

## Validation on read

| Condition | Result |
| --- | --- |
| Record absent for a registered definition | Refuse `missing_ceiling_record` |
| `schema_version` unknown | Refuse `unsupported_schema_version` |
| Names a tool or action the platform does not know | Refuse `unknown_ceiling_entry`, naming it |
| Well-formed | An `AuthorityScope` |

**Never inferred from `ceiling_policies`**, in either direction. That substitution is how a
secrets grant becomes a tool grant without anyone deciding it should.
