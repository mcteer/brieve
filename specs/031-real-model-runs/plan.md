# Implementation Plan: A real model drives a governed run

**Branch**: `spec/031-real-model-runs` | **Date**: 2026-08-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/031-real-model-runs/spec.md`

## Summary

Four moves, in dependency order. **The visibility change** (US4) lands first because it is
hermetic and self-contained: `operator` gains `AUTHORITY_DENIED`/`AUTHORITY_REFUSED`, with the
estate suites' declared roles and ADR-0059's span moving in the same commit — the agreement row
enforces the unity. **The plan subject** (US2) extends the live lane: `must_deny`/`must_decline`
scored under `_subject(pack, "plan")` in addition to `ask`, so plan-role evidence exists to earn
the cell. **The demonstration harness** (US3) is a script with the credential's posture — seed
the live plan cell + a demonstration binding out of band, dispatch bounded runs, restore, then
run the merge gate as proof. **The demonstration itself** (US1) closes it: a dispatched run whose
chooser is a real model, its over-reach refused, its trail read back, 027's T016b closed live.

## Technical Context

**Language/Version**: Python 3.12; bash for the demonstration script (the `infra/bin` idiom).

**Primary Dependencies**: none new. The chooser, credential broker, dispatch and trail all exist.

**Storage**: none new. The demonstration writes matrix/binding records out of band (Vault KV, the
credential's posture — never Terraform state) and restores them.

**Testing**: hermetic rows for the visibility change and lane extension; the live lane for plan
evidence (~10 extra minutes); the demonstration script is itself the US1/US3 validation, with the
merge gate as its final step.

**Target Platform**: the dev enclave; the demonstration dispatches through the real scheduler.

**Project Type**: eval-lane extension + one visibility change + a demonstration harness.

**Performance Goals**: demonstration cost bounded and stated: **2 runs × ≤5 steps** (one clean
run, one over-reach run), ≤ ~15 vendor calls total including retries.

**Constraints**: the merge gate unchanged in what it forbids (FR-007/008); no sealed core
(FR-014); credential never in env/state (FR-001, FR-012); terminal stops only (FR-003).

**Scale/Scope**: ~6 files touched + 1 new script + suites/ADR edits.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | A subject parameter, a scope change, a bash script. |
| II — Total Interception | Pass | Consumed: the real model's choices pass the same `invoke_tool`; a row asserts it live. |
| III — Fail-Closed | Pass | Credential absent → terminal stop; provider fault → terminal stop; no fixture fallback (FR-003). |
| IV — Zero Standing Credentials | Pass | The demo cell/binding are written out of band and torn down; the credential path is ADR-0058's, exercised not changed. |
| V — Sealed Core | Pass — no touch | Trail vocabulary consumed; no payload changes. |
| VI — Lean by Default | Pass | No new components; the standing-demo-definition alternative was rejected partly here. |
| VII — Anti-Fragmentation | Pass | One chooser, one broker, one gate — all consumed. |
| VIII — Eval-Gated Promotion | **Pass — exercised** | The plan cell is earned by new plan-subject evidence; ask-role reuse rejected (030's rule). |
| IX — Evidence Over Claims | Pass | The demonstration IS the evidence; the gate run after teardown is the restoration proof. |
| X — Decision Record Governs | Pass | ADR-0059's span updated with the visibility change, same commit; ADR-0049/0058 consumed. |

**Gate result**: PASS.

## Project Structure

```text
specs/031-real-model-runs/            # plan.md, research.md, data-model.md, quickstart.md,
                                      # contracts/conformance.md, tasks.md

src/core/answering/scope.py           # operator += AUTHORITY_DENIED, AUTHORITY_REFUSED
packs/{vault,terraform}/evals/estate_state.toml  # declared roles reviewed (op cases may now
                                      #   legitimately expect denial records — only if a case's
                                      #   expected set says so; none do today, so likely no-op)
docs/adr/0059-...md                   # span note: operator's visible set grew; suites unchanged
                                      #   unless cases change — the agreement row stays exact

tests/evals_live/test_gates_live.py   # plan subject: must_deny/must_decline scored under
                                      #   _subject(pack, "plan") as well as "ask"
infra/environments/dev/variables.tf   # (comment only) plan cell earned → recorded post-run

infra/bin/model-run-demo              # NEW — seed live plan cell + demo binding (out of band),
                                      #   dispatch 2 bounded runs, restore, run the merge gate
tests/component/test_operator_sees_denials.py  # NEW — visibility change + agreement rows
```

**Structure Decision**: the demonstration is a script in `infra/bin` (the lane-script idiom),
not a conformance row — it costs vendor money and needs an enclave, and the merge gate remains
its own final step. The visibility change touches `scope.py` once; the estate suites need **no
case changes** (measured: no case's expected set gains records — operator's *visibility* grows,
cases' *evidence* doesn't move), so ADR-0059's declared-role span is untouched and only its
prose notes the visibility growth.

## Complexity Tracking

No violations. One measured simplification: the visibility change does NOT ripple into the
suites' declared roles — a case's `asker_role` follows its expected set, and no expected set
changes. The agreement row keeps passing untouched; ADR-0059 gains a dated note, not a new span.
