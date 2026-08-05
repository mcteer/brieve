# Conformance contract: the range, the separation, and the canaries

**Feature**: 037 | **Lane**: merge-blocking (`tests/conformance/intake/`) | **Runs on**: every PR; the range's own posture rows need the enclave and are marked

**Who runs it**: CI's fast lane for everything except the range-posture rows (D6, D7), which
require a live range and run in the enclave lane. Those two are named here so they are not
mistaken for absent.

The stub this contract exists to prevent is **a detonation that runs nothing and reports
clean** — the shape ADR-0047 forbids and the easiest one to ship under time pressure.

## The comparison (US3)

### D1 — Both versions run, and the comparison is over real tasks (FR-011, FR-014)
Assert `tasks_run > 0` and that both candidate and baseline executed. A comparison over zero
tasks is not a clean result; it is no result wearing one.

### D2 — Behavioural differences are reported (FR-011)
A candidate that reaches for a tool its predecessor never touched produces that difference in
the comparison. Constructed rather than hoped for: the fixture candidate differs in a known
way and the row asserts that specific difference appears.

### D3 — A detonation that cannot run blocks (FR-014, FR-024)
Break the range; the candidate does not proceed to the reviewer as clean.

### D11 — The golden corpus has a floor, and it fails rather than warns (FR-011)

**ADR-0053's stated limit is "detonation catches only what the corpus provokes" — this is the
row that puts a number on the corpus side of it.** Without it the honesty of the entire
detonation half rests on whoever writes the tasks, and a corpus of three happy paths satisfies
D1 (`tasks_run > 0`) while provoking nothing.

The floor:

- **at least 8 tasks**, so a comparison has enough surface to differ on;
- **at least 2 that attempt a tool the run's policy denies**, so the comparison can observe
  denial patterns rather than only successes — a corpus that never provokes a denial cannot
  detect a candidate that provokes more of them;
- **at least 1 exercising a must-deny case** from the existing eval suites, so the detonation
  and the platform's own governance floor are measured against the same behaviour;
- **every task produces output comparable across both versions** — a task whose result is
  incomparable contributes a diff nobody can read.

A corpus below any clause **fails**, asserted per clause (the Q7 lesson: aggregate checks hide
one-dimensional breaches).

## The separation (FR-013 — the load-bearing row)

### D4 — Specimen and observer hold different identities (FR-013)
Assert the two are distinct workload identities in distinct allocations. Structural: read the
identities, do not infer them from behaviour.

### D5 — No candidate-authored content reaches the observer (FR-013, SC-005)
The observer's inputs are the run's **records**, not the specimen's output. Asserted by
seeding the candidate's output with a marker and requiring it to appear **nowhere** in the
observer's context or its report.

**This is the row whose loss recreates the vulnerability the gauntlet exists to inspect.** An
observer that ingests candidate output is the injection surface, and every other row can pass
while this one fails.

## The range's posture (`enclave` marked)

### D6 — The range holds no real authority (FR-012, FR-015)
Assert no real authority source is reachable from the range and that it is **not** the
test-only fake — FR-015a, so a later "simplification" that swaps it in fails here rather than
in review.

### D7 — The range reaches no real estate (FR-012)
Egress from the range resolves nowhere real. A range that could reach production is a
detonation chamber with a door.

## Canaries

### D8 — A seeded canary is caught mechanically (FR-012, SC-004)
Detonate a candidate that exfiltrates a canary; `CANARY_CONTACT` is written **without any
person reading anything**. The row asserts detection, not reporting quality.

### D9 — A canary's value never enters the trail (FR-012)
`CANARY_CONTACT` carries the canary's identifier and never its value. A trail that quoted
canaries would become the exfiltration channel it exists to detect.

### D10 — Benign content does not trip canary detection (FR-017, SC-003)
Realistic skill content discussing credentials in documentation must not register contact.
Paired with Q3's false-positive budget: a canary check that fires on the word "secret" would
exhaust the budget on legitimate skills and train reviewers to ignore it.

## Amendment discipline

Q3's thresholds and D10's realistic-content set are the only things here expected to move,
and only in this file, carrying the measurement that motivated the change. Every other row
asserts an invariant; weakening one is a spec change, not a test fix.
