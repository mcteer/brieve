# Data Model: Vault policy authoring

Entities from the spec, shaped by research decisions R1–R14. Nothing here is stored beyond
the audit trail and the trust fabric; the proposal's store keeps reference-not-body, as 041
established.

## PolicyRecord (US1, FR-001–003)

What `vault_policy_read` returns.

| Field | Type | Rule |
| --- | --- | --- |
| `name` | str | as listed by `sys/policies/acl` |
| `state` | enum: `present` \| `absent` \| `protected` | **three states, never two** (FR-003): absent and refused are different answers, and collapsing them is how a denial reads as a gap |
| `document` | str | present only when `state == present`; empty for `protected` — the body never enters the run (R6) |
| `attachments` | list[Attachment] | readable for any state but `absent` |
| `truncated` | bool + note | FR-010: the bound is disclosed when it bites |

**Attachment**: `{kind: token_role | auth_role | entity | group, name: str, mount: str}` —
the places the enclave actually attaches policies (measured in `auth.tf`).

## ProtectedSet (US2, FR-004/006)

| Field | Type | Rule |
| --- | --- | --- |
| `names` | frozenset[str] | read from `harness-authority/data/protected-policies` at run start |
| `source` | str | the fabric path it was read from — recorded so the trail shows *which* list refused |

Invariants:
- Published by the trust-fabric module at apply; a unit row asserts every
  `resource "vault_policy"` name in the module appears in the published list (R4).
- An **unreadable** protected set fails closed: no policy authoring proceeds against an
  empty set, because empty-because-outage and empty-because-nothing-protected are the
  distinction `MatrixSource` already refuses to collapse.
- No member may begin `scratch-agent-` (unit row; FR-020's reserved namespace).

## ScratchCheck (US3, FR-019–022) — exists only inside one handler call

| Field | Type | Rule |
| --- | --- | --- |
| `run_id` | str | the only input to naming |
| `current_name` | str | `scratch-agent-<run_id>-current` — derived, never an argument (FR-020) |
| `proposed_name` | str | `scratch-agent-<run_id>-proposed` |
| `token_role` | const `scratch-check` | `allowed_policies_glob = ["scratch-agent-*"]`, TTL 60s, `no_default_policy` |
| `queried_paths` | list[str] | stanza scan ∪ diff-touched, capped, truncation disclosed (R10) |

State transitions — the whole lifecycle inside `vault_policy_impact` (R1):

```text
derive names → write current → write proposed → mint token(current) → query
→ mint token(proposed) → query → [finally] delete proposed, delete current
```

- Never attached to any entity, role, or auth mount (FR-021) — nothing in the sequence has
  an attach step, and the Vault grant carries no capability that could add one.
- An interrupted call orphans at most two policies and two ≤60s tokens; the sweep (R11)
  removes the policies, the TTL removes the tokens (FR-022/023).

## ImpactResult (US3/US4, FR-007–010)

Platform-composed from Vault's answers; the model never writes it (R9).

| Field | Type | Rule |
| --- | --- | --- |
| `path` | str | as queried; globs labelled `as-written` |
| `current` | frozenset[str] | capabilities under the current body; empty set for a new policy |
| `proposed` | frozenset[str] | capabilities under the proposed body |
| `granted` | frozenset[str] | `proposed − current` — FR-009's "newly permitted", stated not inferred |
| `revoked` | frozenset[str] | `current − proposed` |

An `ImpactResult` that could not be produced is **not represented** — there is no
`unavailable` state, because FR-008 refuses the proposal instead of publishing a gap.

## PolicyAuthoringRequest (US2, FR-004/005) — extends 041's request, does not replace it

| Field | Type | Rule |
| --- | --- | --- |
| *(all of 041's `AuthoringRequest`)* | | `validate()` runs first, unchanged (FR-014) |
| `target_policy` | str | the policy the change is about; `∈ ProtectedSet` refuses `policy_protected` **before anything is read** (US2-1) |

## PolicyProposal (US4, FR-011–013) — 041's `Proposal`, consumed

No new dataclass. The composition adds:
- the impact evidence section to the PR body (platform-authored, R9),
- citation resolution against the pinned corpus at composition; zero resolutions appends
  the FR-012 disclosure to `Proposal.disclosures`,
- the existing containment scan runs unchanged over the authored files (FR-014).

Refusal vocabulary added (all carried on existing error types, closed-vocabulary rows):
`policy_protected`, `policy_absent` (a state, not an error), `impact_unavailable` (FR-008),
`policy_invalid` (Vault's parser refused the document — a policy error, never an impact
result), `scratch_name_forged` (an argument tried to name a scratch policy; layer-2 hook).
