# Conformance: Audit egress for tamper-evidence

**Feature**: `specs/015-audit-egress` | **Date**: 2026-07-30 | **Status**: In force

The point of this contract is the credential boundary: **every row here runs against a live
second store holding credentials the platform does not have.** A row against an in-process
double would prove the comparator compares; these rows prove the *separation* — which is the
property ADR-0055 exists to establish, and the one a fake cannot express. The rows live in
`tests/conformance/evidence/`, `host_enclave` (they hold the collector administrator's
credential to arrange tampering, which the platform must never hold), and the directory is
wired into the Makefile's host lane **in the same change that creates it** — "already named by
a lane" and "named by a lane that will run this row" are different questions (014's lesson,
recorded in `tasks.md` there).

## The rows

| Row | Asserts | Via |
| --- | --- | --- |
| Everything ships, fields intact | Every entry a run writes appears at the destination with all chain fields byte-identical; head observations present (SC-001, FR-002/003) | Run real work; read the destination under the collector admin credential; compare |
| The second copy stands alone | The destination's chain verifies using only destination contents (SC-002) | `verify_chain` over shipped rows, no local read |
| A rewrite is named, not sensed | Rewrite one local entry (as the platform DB admin — the threat actor); reconciliation names the stream and seq (SC-003) | `entry_mismatch` finding |
| The consistent truncation is caught | Delete the newest local entries AND lower the local head to match — the rewrite that defeats every local mechanism; reconciliation reports `local_truncated` (SC-004) | Shipped head observations are the witness (D5) |
| Append is all the platform can do | The shipping credential's `UPDATE` and `DELETE` are refused at the destination; a deliberately writable destination is reported `non_compliant`, naming why (SC-005) | The probe, run as the platform |
| Unprobeable is not protected | A destination that cannot be probed reports `unverified`, and posture does not claim tamper-evidence (SC-005a, FR-020b) | Point the probe at a store that refuses the probe stream |
| Absent is stated, not defaulted | No destination configured → posture `absent` (SC-006, FR-009) | Unset the egress config; read the posture |
| Reconciliation is audited, refusal recorded | Every reconcile run appears as `AUDIT_RECONCILED` naming basis and caller; an unauthorized on-demand attempt is refused and the refusal recorded (SC-007, ADR-0035) | Read the trail through the evidence path |
| Lag is not divergence | Reconcile concurrently with active writing: zero false findings; the tail reads as backlog (SC-008, FR-013) | Write while reconciling |
| Nothing is lost to an outage | Take the destination down mid-run; runs complete; backlog rises and is observable; on return, every entry written during the outage arrives; none lost (SC-009/009a, FR-014a/015/016) | Stop the collector container; resume it |
| **The running service ships, under its own identity** | The mcp allocation — not the row — moves entries to the destination, holding the workload identity the egress policy names (FR-005, ADR-0048) | Write to the first copy; ship nothing; wait for the service's own supervisory pass |
| Capture failure refuses the step | With the LOCAL append failing, the step is refused rather than proceeding unrecorded (SC-009b, FR-014) | Hermetic — the inherited `evidential_gap` path (research F2), asserted so the inheritance is a row rather than a belief |

**The air-gapped shape is the suite's own shape** (spec US5, scenario 1). The dev collector
binds to the local network only, and every row above runs against it with zero egress beyond
the boundary — so "an air-gapped estate still has a second copy" is demonstrated by
construction rather than by a dedicated row, and this sentence is where that claim lives
rather than being implied.

## Break fixtures — applied, observed, reverted (2026-07-30)

| Fixture | Outcome |
| --- | --- |
| The shipper advances the watermark before delivery confirms | **Caught.** `test_row_an_outage_loses_no_entries_and_stops_no_runs` fails: the outage's entries are never re-attempted, which is silent loss. |
| Head observations become an upsert | **Cannot be applied.** The destination's grant refuses `DELETE` and `UPDATE` on `shipped_head_observations` (SQLSTATE 42501), so the shipping pass fails loudly instead of the detection degrading quietly. The property is enforced by Postgres, not by the Python remembering to append. |
| The probe is replaced by a config check | **Caught.** Both `test_row_a_writable_destination_is_reported_non_compliant` and `test_row_an_unreachable_destination_is_unverified_never_verified` fail — a probe that trusts configuration reports `verified` for a destination the platform can rewrite and for one that does not exist. |
| The reconciler treats all tail gaps as pending | **Caught twice.** The live `test_row_the_consistent_truncation_is_reported` and the hermetic `test_the_consistent_truncation_is_caught_by_the_shipped_head` both fail. |

The second fixture is the more interesting result. It was expected to make a row go green
while the attack succeeded; instead it could not be written at all, because the same
append-only grant that stops an attacker also stops the implementer. That is the difference
between a property held by convention and one held by the database.

Applying the first fixture also exposed a gap in the truncation row, now closed: the row
tampered and reconciled without shipping again, and the real supervisory loop does ship
again. Shipping after the tampering is the attacker's best remaining move, so the row makes
it.

## Why the service row exists

Every other row here calls the ship pass itself. All of them passed while the running mcp
service had **never shipped a single entry**: its credential loader read `VAULT_TOKEN` from
the environment, which a host process running a row always has and an allocation never does.
The service reported ABSENT on every pass — correctly, and uselessly — and no row was
watching the one actor that matters in production.

That is the fourth time this repository has paid for the same shape: `resume_run` with no
production caller (014), a sweeper that had never dispatched since 009, an observer the
protocol could not call, and this. A capability that is correct, tested, and wired to
nothing passes everything except use.

## What these rows do not prove

- **The lag window.** An entry destroyed locally before its first delivery, with head and
  watermark adjusted consistently, never existed anywhere (research F4). Bounded by the ship
  interval, surfaced by the backlog observable, and accepted by clarify Q1's decision that
  delivery must not gate the platform's availability. Stated here because a contract that
  implied otherwise would be the overstated claim this platform legislates against.
- **Organizational separation of administrators.** The dev enclave demonstrates *credential*
  separation — the platform's credentials cannot alter the destination. Whether the
  destination's administrators are actually different people is a deployment property no test
  in this repository can observe.
- **Which copy is right.** Reconciliation reports that the copies differ, not which one is
  honest. A compromise of both administrative domains defeats this, by design and by ADR-0055's
  own admission.

## Who runs these

| Where the change comes from | What covers these rows |
| --- | --- |
| Same-repo branch or pull request | CI's enclave lane (`make conformance`, host_enclave line — wired with the directory's creation) |
| Fork pull request | The agent harness in the IDE, per `AGENTS.md` |
