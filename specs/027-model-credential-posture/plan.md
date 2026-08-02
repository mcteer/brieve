# Implementation Plan: How the platform holds a model credential

**Branch**: `spec/027-model-credential-posture` | **Date**: 2026-08-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-model-credential-posture/spec.md`

## Summary

The platform gets its first working credential broker, and a person finally gets an answer from
the deployed surface. One vendor credential lives in the trust store
(`model-credentials/<vendor>`), operator-written and rotated in place; a workload obtains it **at
task start** under its own attested identity, holds it in process memory for exactly one task, and
never persists it anywhere — no checkpoint, no log, no trail, no model context. Revocation is a
store operation: rotate or delete, and the next task's fetch refuses `credential_unavailable`,
distinguishable from 026's `unqualified_cell` and from a vendor outage. The same reader serves the
ask path (per ask, in `served.py`) and the run path (per allocation, in the entrypoint), because
two mechanisms for one question is the fragmentation Principle VII forbids.

**Two documents change alongside the code, in the open**: ADR-0058 records the decision, and the
constitution moves to v1.4.0 — *"exactly two named exceptions"*, and the static-API-key sentence
rewritten rather than read around (FR-002).

**Research reframed the feature** (F1): the "TFE broker precedent" is a Protocol with no
production implementation, so this is the **first** brokered credential, and its shape becomes the
precedent the TFE path later inherits.

## Technical Context

**Language/Version**: Python 3.12.

**Primary Dependencies**: **None added.** The store is the existing Vault; both workload roles
already authenticate with attested identity; the readers follow the fabric pattern.

**Storage**: one KV v2 secret at `model-credentials/<vendor>`. No new mount engine, no database.

**Testing**: pytest — component rows for the reader and refusal vocabulary; conformance rows for
never-persisted / never-leaked, the three-refusal distinction, revocation-without-restart, and
both-paths-one-mechanism; the readability row pattern for the new Vault path.

**Target Platform**: the served MCP surface and the dispatched allocation; Terraform for the
mount, policy, and (dev) placeholder.

**Project Type**: governed agent runtime — authority posture plus two call-site integrations.

**Performance Goals**: one Vault read per task. The surface already performs fabric reads per ask
(026); this adds one more of the same class.

**Constraints**: blocking lanes credential-free (FR-011); eval lane exempt and says so at the lane
(FR-013a); no credential value in trail/log/checkpoint/context (FR-008, SC-005); 026's binding
order consumed unchanged — cell first, then credential, then vendor.

**Scale/Scope**: one reader module in `core/authority/`; `client_and_model` gains `api_key`;
`served.py` builds the provider per ask; the entrypoint fetches before `build_chooser`; one
sealed-core payload addition (`model_authority` on `ASK_ANSWERED`; `MODEL_GATE` deferred — see
Complexity); ADR-0058 + constitution v1.4.0; Terraform mount/policy/seed; rows.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | A KV read and two call-site integrations. No framework, no dependency. |
| II — Total Interception; One Governed Tool Layer | **Pass** | No tool or hook is touched; the model call keeps its 026 gate and gains its credential gate. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | No credential → refuse `credential_unavailable`, before any vendor contact. No fallback to env, no cached copy — a fetch that fails, fails the task. |
| IV — Zero Standing Credentials; Authority Per Task | **This feature amends it, in the open — which is the requirement, not a violation.** | As written, *"static API keys are prohibited without exception"* and any vendor key cannot coexist. FR-002 makes the reconciliation explicit: ADR-0058 + constitution v1.4.0, MINOR (adds a named exception), Sync Impact Report, and the gate below **names the amendment as a deliverable rather than treating the principle as satisfied**. Until the amendment merges, the principle stands and the platform stays as it is — the amendment and the capability land together or not at all. |
| V — Sealed Core, Versioned Seams | **Pass, review owed and this time it gates the PR.** | `ASK_ANSWERED` gains `model_authority` (a reference, never a value) — the fourth additive touch in four features. **Security review: Dan McTeer, BEFORE merge**, per the discipline the just-closed review established. The pattern (this record accumulates ask facts because asks have no run) was examined in that review and held. |
| VI — Lean by Default | **Pass, and a rejection is recorded.** | No new operated component. A model gateway was rejected by name: it moves the key outward without removing it, and would need the named trigger this table exists to demand. |
| VII — Anti-Fragmentation | **Pass** | One reader, both paths. The eval lane's exemption is a *stated boundary*, not a second mechanism — it predates this feature and stays a human-run lane. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | Which model may be called stays the matrix's (026, consumed). This feature only supplies the means to call one. No gate changes. |
| IX — Evidence Over Claims | **Pass** | `model_authority` puts *how the call was permitted* beside *which cell allowed it*, as a reference. Three failure causes get three trail-visible dispositions. |
| X — The Decision Record Governs | **Pass — by adding to it.** | ADR-0058 is the motivating record the amendment cites. ADR-0044 is consumed: its federate-or-broker rule routes models to the broker branch; the ADR gains a pointer, not a rewrite. |

**Gate result**: **PASS — proceed to Phase 0**, with the explicit condition that **the
constitution amendment is a deliverable of this feature** and merges with it. A plan that shipped
the capability first and the amendment later would have the platform contradicting its
constitution in the interval, which is US3's failure mode verbatim.

**Obligations created, named now**: Principle V review (Dan McTeer, before merge); the
constitution amendment PR (MAJOR-review rules do not apply — MINOR — but security-maintainer
review does, same reviewer); the revocation demonstration on a live enclave (Dan McTeer, part of
the enclave lane).

## Project Structure

### Documentation (this feature)

```text
specs/027-model-credential-posture/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── conformance.md   # Phase 1 — the rows this feature binds
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
docs/adr/0058-model-credential-brokering.md   # NEW — the motivating record
.specify/memory/constitution.md               # v1.3.0 → v1.4.0: two named exceptions;
                                              #   the static-key sentence rewritten (FR-002)

src/core/authority/
└── model_credential.py   # NEW — BrokeredModelCredential: read model-credentials/<vendor>
                          #   at task start under the caller's own identity; refuse
                          #   `credential_unavailable` when absent/unreadable; NEVER cache.
                          #   Beside ask_binding.py — it is authority-domain, and the
                          #   never-acts rows keep it out of core/answering (025's rule)

src/adapters/anthropic_scorer.py   # client_and_model gains api_key: str | None = None;
                                   #   the eval lane keeps the env path — FR-013's exemption
src/adapters/anthropic_answering.py  # providers accept the fetched key
src/adapters/model_chooser.py      # build_chooser threads an explicit key for non-fixture
                                   #   models — never ambient env in production paths

src/surfaces/mcp/served.py    # builds the ask provider PER ASK through the reader; wires
                              #   the credential source beside ask_authority
src/surfaces/dispatch/entrypoint.py  # fetches before build_chooser when the resolved
                                     #   model is non-fixture; material dies with the
                                     #   allocation (an allocation IS one task)

src/core/audit/schema.py      # SEALED CORE — ASK_ANSWERED payload gains model_authority
                              #   (reference, never value). MODEL_GATE deferred (Complexity)
src/core/answering/record.py  # record_ask carries it

infra/modules/trust-fabric/   # model-credentials mount path + policy (exact-path AND glob,
                              #   020's trap); grants to mcp-surface and the run role
infra/environments/dev/       # dev placeholder credential (see tasks: seeded or absent is
                              #   a deliberate choice, not a default)

tests/component/              # reader, refusal vocabulary, no-cache
tests/conformance/answering/  # credential_unavailable ≠ unqualified_cell ≠ vendor-down;
                              #   never-persisted / never-leaked rows; revocation row
tests/conformance/identity/   # readability row for the new path, as-applied
tests/evals_live/             # the exemption STATED at the lane (FR-013a) — comment + row
```

**Structure Decision**: the reader sits in `core/authority` beside the ask binding for the same
reason the binding does — it is an authorization concern, and 025's never-acts rows forbid the
answering path any import containing `authority`, which keeps the credential structurally out of
reach of the path that uses its product. Both call sites fetch at the last responsible moment
(per ask; per allocation) so the material's lifetime is the task's, which is the whole posture.

## Constitution Re-Check (post-Phase 1)

**Re-evaluated after `data-model.md`, `contracts/conformance.md`, and `quickstart.md`. Still
PASS under the same explicit condition** — the amendment ships with the capability. Phase 1 added
no dependency, no component, no second mechanism.

One emphasis sharpened: **Principle III's watch item is the fallback-to-env temptation.** The
adapters currently read env keys for the eval lane, and the easiest bug in this feature is a
production path that quietly falls back to `EVAL_PROVIDER_API_KEY` when the broker fetch fails.
The contract carries a row asserting the fetch failure refuses rather than falling back, with the
env var deliberately set in the test.

## Complexity Tracking

*No Constitution Check violations. Table intentionally empty.*

Two judgment calls, recorded because each could reasonably have gone the other way:

| Decision | Why | Alternative rejected because |
|---|---|---|
| `MODEL_GATE` does **not** gain `model_authority` in this feature | The ask path has a user today; no run has ever bound a real model, so the run-side record would be written by nothing and verified by nothing — a field earning its review with no row able to exercise it | Adding both now "for symmetry" is a sealed-core change without an observer, which is how documented payloads drift from written ones |
| The spec's FR-001a is amended, surgically, to the precedent-honest form | A static key is not derivable (research F2); "cannot read what it was derived from" is unimplementable without a proxy that merely relocates the key | Keeping the wording and building the proxy adds an operated component to satisfy a sentence the precedent itself does not satisfy |
