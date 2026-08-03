# ADR-0059: A cell's estate evidence spans the asker roles its cases declare

- **Status**: Accepted
- **Date**: 2026-08-02
- **Relates to**: [ADR-0022](0022-qualified-model-matrix.md), [ADR-0039](0039-per-role-model-bindings.md), [ADR-0035](0035-audit-as-a-governed-read-path.md), [ADR-0018](0018-grounded-reporting.md)
- **Requirements**: R10

## Context

On 2026-08-02 this platform earned its first two `qualified_by = "live"` matrix cells —
`anthropic/claude-opus@5` for the `ask` role, vault and terraform packs. They were bound the same
day and were answering real questions through the deployed portal within hours. The same day, a
measurement found that three-fifths of the estate evidence behind them was gathered for a role the
platform does not grant the people asking.

The mechanics: the estate eval's scorer handed the answering function the fixture's records whole.
Production narrows first — `visible_event_types(roles)` decides what an asker may see before the
answering function receives a record — and the fixture holds two authority-record types that the
`operator` role cannot see at all. Six of ten estate cases across the two packs expect exactly
those records. So the suite demonstrated answering over evidence an operator would never receive,
and a cell qualified by that suite claimed more than the evidence showed.

This is [024](../../specs/024-portal-answering/spec.md)'s own finding one layer in. That feature
exists because the live lane scored a path the product does not take; its remedy moved the scorer
onto the product's answering *function*, which stopped one call short of the path a person's
question actually travels. The lesson, now twice-taught, is that an eval's fidelity claim extends
exactly as far as the path it drives, and not one call further.

There is also a subtlety the fix had to respect: the asker's role is **not** the matrix's role.
The matrix's `role` column is the *agent* role — `ask`, `plan`, `judge` — the capacity in which a
model acts. The asker's role is a *visibility*: what the person whose question it is may see. One
`ask` cell serves operators and compliance analysts alike; which records the answer may rest on
differs per asker, and the eval has to be honest about which askers its evidence covers.

## Decision

**Every estate case declares the role that could ask it, the scorer narrows the fixture to that
role's visibility before the answering function runs, and a cell's estate evidence is understood
to span exactly the asker roles its cases declare.**

- The declaration (`asker_role`) is required for estate cases, drawn from the platform's own role
  vocabulary, and never defaulted — a defaulted role would be the implicit assumption this
  decision removes, reappearing one field over.
- The tag follows the case's **expected reference set, not its prompt**. Twice during this
  feature a case read as operator-shaped while its expected references included an authority
  record: the question is anyone's, the case is not.
- A case expecting a record its declared role cannot see **refuses to run**, loudly, naming the
  case and the invisible type. Exclusion-by-silence would rebuild the defect with better manners.
- **Qualification requires every declared role's subset to pass.** A model that answers well for
  compliance analysts and poorly for operators is not qualified for `ask`.
- **The matrix schema is untouched.** The `role` column keeps meaning the agent role; the asker
  roles a cell's evidence spans are recorded here and pinned by a test that fails if the suites'
  declared roles drift from what this record names — today, `operator` and `compliance-analyst`.

**What the estate eval still does not exercise, stated as part of the decision**: the governed
read and its access record, temporal window resolution, and the per-type read bound. Driving those
would put an evidence store inside the eval and write an access record per scored case — a change
to what a scoring run *does*, not only what it checks — and a five-record fixture could not
exercise a bound regardless. The gap is written at the suites and in the scorer, because the
unstated version of exactly this gap is what this record exists to end.

## Consequences

**What it makes true.** A `qualified_by = "live"` estate claim now means: demonstrated on
role-narrowed evidence, for each asker role the suite declares. Whoever reads the matrix can know
which askers the evidence covers by reading the suites, and a drift between the two fails a test
rather than accumulating silently.

**What it costs.** Case authors carry a new obligation — the tag, measured against the expected
set — and the two live cells' evidence is retroactively subject to re-examination rather than
grandfathered (the corrected lane re-runs under a named human; failure for any role subset
withdraws the affected cells). Withdrawal unbinds the deployed ask until an operator rebinds,
which is the mechanism working and is stated here so nobody discovers it mid-question.

**What it forecloses.** Per-visibility matrix cells were rejected: an `ask` cell serves whichever
role asks, and a cell per (pack × model × agent-role × asker-role) would multiply the matrix's
maintenance combinatorially to record a distinction the suite already carries. Smuggling the
asker roles into the cell's `judge` field was rejected as a lie of position. And re-aiming the
suite at a single role was rejected because the platform grants two: scoring only the analyst
leaves the path most users take unqualified, and scoring only the operator discards
authority-question answering unscored.

## Notes

The declaration and narrowing live in `core/evals/suites.py` and `core/evals/scoring.py`; the
agreement test is `test_the_declared_roles_match_what_the_adr_says_the_evidence_spans` in
`tests/component/test_estate_eval_scores_visibility.py`.

The naive check — re-running tagged suites without the narrowing — is vacuous and recorded as
such in the feature's conformance contract: correctly tagged cases rest only on visible records
either way, so the filter is invisible to verdicts. The checks with teeth observe the provider's
input and the load-time refusal.

Whether `operator` should see authority records was the open decision 029 recorded — **answered
2026-08-03 by 031**: `operator` gained `AUTHORITY_DENIED` and `AUTHORITY_REFUSED` (what happened
to *your* runs is yours to ask about), while `AUTHORITY_ISSUED`, `AUTHORITY_EXPIRED` and the
grant/change records stay analyst-only. **The span this record names is unchanged** — no estate
case's expected set moved, so no `asker_role` moved, and the agreement test kept passing
untouched, which is exactly the "single deliberate step" this paragraph asked for: one visibility
set, one focus-row update, and this note, in one commit.
