# Conformance: Vault policy authoring (042)

Rows are **V1–V18** (hermetic unless marked), plus live legs **PL1–PL3**. Each row is
blocking from the moment its feature exists (ADR-0047); none may be stubbed green.

**Named runner (constitution v1.1.0)**: every row no automated check executes — the
`enclave`-marked rows and the PL legs — is run by **Dan, before merge**, with the per-row
outcome recorded here in the implementation PR.

## The safety case (US2 — FR-004/005/006, SC-002/003)

| Row | Asserts | Mechanism |
| --- | --- | --- |
| V1 | A request whose `target_policy` is protected refuses `policy_protected` before any read — the provider/tool layer records zero calls | request validation (R5 layer 1) |
| V2 | `author_file` arguments naming a protected policy refuse **in the hook pipeline** and the attempt is recorded | GOVERNANCE pre-hook (R5 layer 2) |
| V3 | **The refusal can lose**: with the 042 hook removed from registration, V2's scenario passes authoring — this row fails. SC-003's row | remove-and-assert |
| V4 | A planted instruction in the subject naming `agent_ceiling` is recorded by the injection lens and changes nothing; escalation to a tool call lands in V2 | inherited lens + hook |
| V5 | The protected set is read from the fabric, and an unreadable fabric fails closed — refusal, not an empty set | ProtectedSet invariant |
| V6 | Every `resource "vault_policy"` name in `infra/modules/trust-fabric/` appears in the published protected list — drift fails the merge | unit scan (R4) |
| V7 | No trust-fabric `vault_policy` name begins `scratch-agent-` | unit scan (FR-020) |

## Reading (US1 — FR-001/002/003)

| Row | Asserts | Mechanism |
| --- | --- | --- |
| V8 | `vault_policy_read` is a registered, hook-wrapped tool; invoking it produces the ordinary intent/result bracket | registry + trail |
| V9 | The three states are distinct: `present` (body included), `protected` (no body, named as protected), `absent` — and no response contains a secret value or a `secret/` path read | tool contract |
| V10 | Attachment output truncates at the bound with the truncation disclosed | FR-010 |

## The instrument (US3 — FR-007/008/019–025, SC-004/005/010/011/012)

| Row | Asserts | Mechanism |
| --- | --- | --- |
| V11 | `vault_policy_impact` derives scratch names from the run id; an argument attempting to supply one refuses `scratch_name_forged` | hook + handler |
| V12 | The impact result carries `granted`/`revoked` per path — a widening change shows the widening (SC-009: the row fails if the evidence would read identically without the impact) | ImpactResult |
| V13 | An impact check that cannot run refuses the proposal: no `ImpactResult`, no publish (`impact_unavailable`) — never a fabricated result | FR-008 |
| V14 | A syntactically invalid proposed policy is reported as `policy_invalid` from Vault's parser, never as an impact result | edge case |
| V15 **enclave** | Against the real Vault: the full scratch lifecycle runs; after the call, zero `scratch-agent-*` policies remain and the minted tokens are expired or revoked. **Fails, never skips, when Vault is absent** (SC-007) | live |
| V16 **enclave** | A scratch write naming a protected policy is refused by **Vault's own ACL** with the platform hook disabled — the product-level back-stop holds independently (FR-025, SC-012) | live |
| V17 **enclave** | An orphaned scratch policy (planted by the row, not left by chance) is removed by the sweep and the removal is audited (FR-023, SC-010) | live |

## The proposal, and what 041 keeps (US4/US5 — FR-011–015, SC-001/006/008)

| Row | Asserts | Mechanism |
| --- | --- | --- |
| V18 | The composed PR body carries diff + impact evidence + citations; citations resolve against the pinned manifest; zero resolutions appends the FR-012 disclosure; **no secret value and no trust-fabric policy body appears** (SC-006, asserted over the composed body, not claimed) | composition |

- **SC-008 is a diff row**: 041's conformance files unchanged from the merge-base —
  same shape as 043's R9, including the `origin/<base>` fallback that row had to learn.
- **FR-014**: a row asserts the registry holds exactly one publisher and `open_proposal`
  is it.

## Live legs (named runner: Dan)

| Leg | What runs |
| --- | --- |
| PL1 | `make evals-smoke`-shaped single pass: one impact check against the enclave Vault, raw capability answers printed, before anything bigger |
| PL2 | End to end: policy-repository subject → read → author → impact → real PR opened via 041's publisher; reviewer answers SC-001's three questions from the PR alone |
| PL3 | V15–V17 executed against the enclave, outcomes recorded here |

## Out of scope, recorded

Requester-scoped reads (FR-018, owed — ADR-0044 territory); the intake surface; any second
publishing path; Terraform's impact instrument (its oracle is a fixture — ADR-0047).
