# Conformance contract: a run's write grant names only its own workspace

**Feature**: 054 | **Date**: 2026-08-27 | **Spec**: [../spec.md](../spec.md)

Gate rows attach as the feature lands (ADR-0047). Every row names the state in which it fails.

## 1. The rows that matter most are live

The defect was credible because it was **demonstrated** against the live control plane. The fix
is credible on the same terms and no other — a hermetic row asserting a refusal it constructed
itself proves nothing about Vault's answer.

| Row | Asserts | Fails when | FR / SC |
| --- | --- | --- | --- |
| **E1** | A run-shaped authority attempting **read** on another run's workspace is refused, live | the estate-wide grant is still in force | FR-001, SC-001 |
| **E2** | The same for **write** | as above | FR-001, SC-001 |
| **E3** | The same for **delete** | as above | FR-001, SC-001 |
| **E4** | The same authority **succeeds** on its own workspace | the narrowing went too far and the measurement is broken | FR-001, SC-002 |
| **E5** | Removing the narrowing makes E1–E3 pass again | the refusal comes from something other than this feature | FR-004, SC-003 |
| **E6** | A read a run could make before is still permitted | reads narrowed by accident | FR-006, SC-005 |
| **E7** | The sweeper still lists the namespace | the run's narrowing narrowed the service role too | FR-008 |

**E1–E3 replay the exact actions that returned 200, 200 and 204 on 2026-08-27.** Same shape as
018's registry-isolation rows: a real attempt under a real run's authority, against the live
control plane, with every refusal observed.

**E4 and E6 are not optional.** A grant that reaches nothing refuses everything, and would
satisfy E1–E3 while breaking the product. E5 is the safety case being able to lose.

## 2. Hermetic rows

| Row | Asserts | Fails when | FR / SC |
| --- | --- | --- | --- |
| A1 | A run whose requested tools declare no write path is manufactured no write grant | write authority is handed out by default again | FR-012, SC-007 |
| A2 | The decision reads requested tools, not what the model later called | authority starts depending on model behaviour mid-run | FR-013 |
| A3 | A re-mint reproduces the recorded scope and never re-derives | drift becomes possible on resume, renewal or retry | FR-017, SC-009 |
| A4 | A widened re-mint is **refused**, and the refusal is detectable | the guarantee rests on nothing having gone wrong yet | FR-017 |
| A5 | Failed manufacture stops the run with a distinct reason | a failure is reported as another failure, or proceeds | FR-005, SC-004 |
| A6 | Failed renewal is handled as failed manufacture | a mid-Build expiry leaves a half-written measurement | FR-015 |
| A7 | No wider authority exists to fall back to | an estate-wide grant is retained "just in case" | FR-005 |
| A8 | The `run_id_forged` guard still refuses | this feature is read as replacing the layer above it | FR-007 |
| A9 | The workspace derives from the manifest's declared `paths` | a second place to say what a tool touches appears | FR-010 |
| A10 | A derived workspace contains no wildcard | a pattern survives into the object built to remove one | FR-001 |

**A10 is the one to keep if any are cut.** A workspace that still holds `*` would pass every
other row here and grant exactly what the feature exists to stop.

## 3. What the branch in the plan owes this contract

[R2](../research.md) decides the mechanism, and the rows above are written to be
**mechanism-independent** — they assert what a run may reach, not how the grant was made. That
is deliberate: a contract naming a JWT would have to be rewritten if the cheap path wins, and
would quietly argue for the expensive one.

Two rows are owed **only if R2 fails** and 016's substrate is built:

| Row | Asserts |
| --- | --- |
| E8 | A run presents its own attested identity; no credential is handed to the allocation (ADR-0058) |
| E9 | The mint path is bounded — a run cannot mint authority naming another run's workspace |

## 4. Named runner

Dan McTeer (maintainer). E1–E7 fail loudly when the enclave is absent; they do not skip green.

| Row | Named runner | Status |
| --- | --- | --- |
| E1–E7 | — | pending |

## 5. Stability commitments

- **The recorded scope is a record.** FR-011 is answered from it, so its shape is pinned here
  rather than left to implementation: `run_id`, `paths`, `derived_from`.
- **Read scope is unchanged.** Any row that would pass by narrowing a read is invalid.
- **`b7c2a2f` is consumed, not replaced.** FR-007.

## 6. Security-maintainer review

**Required.** This changes the authority a dispatched run holds and the trust fabric that
bounds it — sealed core under Principle V on two counts, plus a new record shape. The review
should be asked specifically whether the derived workspace can be induced to widen, since that
is the failure that would leave every row here green.
