# Implementation Plan: A run's write grant names only its own workspace

**Branch**: `spec/054-run-scoped-write-grant` | **Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/054-run-scoped-write-grant/spec.md`

## Summary

Every dispatched run holds `sys/policies/acl/scratch-agent-*` with `create`, `update`, `delete`
and `read`, estate-wide, while the names it protects are already per-run. Demonstrated
2026-08-27: a run-shaped token read (200), overwrote (200) and deleted (204) another run's
measurement policy. The pipeline route is closed (`b7c2a2f`); this is the layer beneath it.

**Phase 0 changed the shape of this plan and cut its likely cost.** ACL policy templating —
the obvious cheap answer — is **rejected on measurement**: every dispatched run shares one
entity and one alias, because Nomad's workload identity presents the **parent** job id, which
`auth.tf` already records as a thing somebody paid for during 010 ([R1](research.md)).

That leaves one question worth answering before anything is built: whether Nomad 2.0.4's JWT
carries a **per-allocation** claim ([R2](research.md)). If it does, the feature is a changed
`user_claim` and a templated policy. If it does not, the fallback is constrained by ADR-0058 —
a token handed to an allocation is a key in its environment — which is what makes 016's
resource-server substrate the expensive-but-correct answer ([R3](research.md)).

**R2 was settled on 2026-08-27: `nomad_allocation_id` is in the claim set, so Branch A is
taken and 016's substrate is not built.** The decision point did its job — the cheap path was
tested rather than assumed, and it works.

Two things came with the answer. Branch A leaves **one permanent Vault identity entity per
run** and nothing prunes them ([R2a](research.md)) — accepted, with a follow-up owed. And
**FR-016 reversed**: a restarted run must *not* reach the previous attempt's workspace, because
an outage restarting a job repeatedly would have every attempt contending for one — this
feature's own defect, self-inflicted.

## Technical Context

**Language/Version**: Python 3.14; HCL for the trust fabric

**Primary Dependencies**: None new. Vault (identity, policies, token roles), Nomad workload
identity, both already operated

**Storage**: The recorded per-run scope ([R5](research.md)) needs a durable home; the run's
existing record is the candidate. No new store

**Testing**: `pytest` — hermetic rows for derivation and refusal codes; **enclave rows** for
the bound itself, in the shape 018 established for registry isolation

**Target Platform**: The enclave. This is trust-fabric configuration plus the code that
derives from it

**Project Type**: Platform authority change — infra plus a narrow core seam

**Performance Goals**: Manufacture is on a run's startup path only when its tools declare a
write path (FR-012), so most runs are unaffected

**Constraints**: Reads must not narrow (FR-006). The sweep keeps its breadth (FR-008). The
`b7c2a2f` guard stays (FR-007). ADR-0058 forbids handing a credential to an allocation

**Scale/Scope**: One namespace, one write capability, two packs — `scratch-agent-*` is the only
write grant a dispatched run carries today

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
v1.6.0 (Last Amended 2026-08-05) — checked against that version.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | Vault performs the bounding; Nomad supplies the identity. The platform derives a scope and presents it. Nothing here reimplements an authorization server — ADR-0056 established that Vault cannot be one, and that finding is consumed rather than revisited |
| II — Total Interception; One Governed Tool Layer | Pass | No tool, transport or egress class changes. `vault_policy_impact` keeps its interface and its meaning |
| III — Fail-Closed, In-Process Enforcement | **The principle this feature serves** | A failure to manufacture stops the run (FR-005), a failed renewal likewise (FR-015), and no wider authority is ever substituted. The honest consequence is stated: a Build that cannot be granted a scoped credential cannot measure a policy's impact, so it stops |
| IV — Zero Standing Credentials; Authority Per Task | **The principle this feature repairs** | Principle IV describes authority manufactured per task. For the one write capability a run carries, it currently is not — the grant is per estate. FR-012 also makes most runs carry *no* write authority, which is stricter than today |
| V — Sealed Core, Versioned Seams | Pass **with obligation** | Touches the trust fabric and the run's authority path. Both are sealed core: this feature has an approved spec, and the implementation PR **must request security-maintainer review**. The recorded per-run scope ([R5](research.md)) is a record shape and is pinned in the contract rather than left to implementation |
| VI — Lean by Default | **Pass** | [R2](research.md) held: a changed `user_claim`, a templated policy, no minting, no transit key, no resource-server profile. The one cost is entity growth ([R2a](research.md)), recorded rather than discovered |
| VII — Anti-Fragmentation | Pass | One mechanism for the one write grant that exists. FR-010 derives from the manifest declaration already in the tree rather than adding a second place to say what a tool touches |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | N/A | No model, no prompt, no pack instruction changes |
| IX — Evidence Over Claims | Pass | The defect was demonstrated, not argued, and FR-003/FR-004 require the fix to be demonstrated on the same terms — a real attempt under a real run's authority against the live control plane, with a row that fails if the narrowing is removed |
| X — The Decision Record Governs | Pass | ADR-0057's trigger 1 has fired and is recorded; only the WRITE case re-opens, which its Decision predicted. ADR-0056's mechanism is consumed. **ADR-0058 constrains the fallback** and is the reason the cheap hand-it-down answer is closed. No Accepted record is contradicted |

**Gate result**: **PASS — proceed to Phase 0.** With one obligation carried below.

### The obligation this plan carried — discharged 2026-08-27

**R2 was a gate, not a research note**, and answering it first is what kept 016's substrate out
of a feature that turned out not to need it. The claim exists; Branch A is taken; Branch B is
struck in `tasks.md` rather than deleted, so the rejection stays legible.

**What replaced it as the thing to watch**: entity sprawl. Nothing prunes Vault identity
entities, and Branch A creates one per run.

## Project Structure

### Documentation (this feature)

```
specs/054-run-scoped-write-grant/
├── spec.md
├── plan.md              # this file
├── research.md          # R1–R6
├── data-model.md        # run workspace, scoped grant, recorded scope
├── quickstart.md        # reproduce the defect; verify the bound
├── contracts/
│   └── conformance-run-scoped-write.md
└── checklists/requirements.md
```

### Source Code (repository root)

```
infra/modules/trust-fabric/
├── scratch.tf                    # the estate-wide grant this feature replaces
└── auth.tf                       # user_claim / claim_mappings — the R2 branch lands here

src/core/authority/               # derivation of a run's workspace from declared paths
src/core/packs/manifest.py        # the per-run form of the `paths` declaration (R4)

tests/conformance/authority/      # the bound, in 018's shape — a real attempt, live
tests/unit/                       # derivation, re-mint stability, refusal codes
```

**Structure Decision**: Trust fabric plus a narrow authority seam. The tool layer, the packs'
instruction content and the eval lanes are untouched.

## Complexity Tracking

| Question | Answer |
| --- | --- |
| Why not ACL templating, which is nearly free? | Measured and rejected: every dispatched run shares one entity because Nomad presents the parent job id ([R1](research.md)). Two concurrent runs would get identical grants naming each other's workspace — the same defect, harder to see |
| Why not have the surface mint a token and pass it down? | ADR-0058, recorded in `auth.tf`: a key handed to an allocation is a key in the allocation's environment ([R3](research.md)) |
| Why is 016's substrate not simply adopted? | Because FR-009 requires the cheapest sufficient mechanism, and [R2](research.md) is unresolved. Adopting it first would be justifying parked work |
| Why store the derived scope rather than compare derivations? | FR-017 requires every re-mint to be scope-identical. Storing one derivation removes the drift class; comparing two only detects it when the comparison is right and always runs ([R5](research.md)) |
| Why do most runs end up with less than today? | FR-012. Today every dispatched run carries the estate-wide write grant whether or not it will ever write. Deriving from requested tools means most carry none |

## Post-design Constitution re-check

*Run after Phase 1 artifacts.*

**Verdict: PASS**, and Principle VI is no longer conditional — [R2](research.md) resolved in
favour of the small change.

One verdict moved. **Principle V's obligation hardened**: Phase 1 gives the recorded per-run
scope a defined shape, and because an auditor answers FR-011 from it, it is a record rather
than an implementation detail. It is pinned in
[contracts/conformance-run-scoped-write.md](contracts/conformance-run-scoped-write.md) and the
implementation PR requests security-maintainer review on that basis as well as on the authority
path.

Nothing in Phase 1 required a new ADR. ADR-0057's amendment already records the re-opening,
ADR-0056 supplies the mechanism if R2 fails, and ADR-0058 constrains the alternative — three
Accepted records doing exactly what the decision record is for.
