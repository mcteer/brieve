# Research: 030 — the estate eval scores the real path

**Phase 0.** Measured against merged `main` on 2026-08-02, after 029.

---

## F1 — Where the gap is, precisely

**Measured**: `EstateAnsweringScorer._answer` calls
`answer_estate_question(question=case.prompt, records=self._estate.records, provider=...)` — the
fixture's records, whole. Production (`estate_answer_for`) computes `visible_event_types(roles)`,
refuses on empty, reads through `read_evidence_for` (access record, narrowed request), resolves the
temporal window, and applies 029's per-type bound — all before `answer_estate_question` sees a
record. The scorer skips every one.

**Decision**: close the piece this feature's finding is about — role visibility — at the scorer,
by narrowing the fixture records to the case's declared role before the answering function runs.
The rest of the path stays unscored **and stated** (F5): driving it would need an evidence store
inside the eval and an access record per scored case, which changes what a scoring run *does*.

## F2 — The case schema can carry the role, and validation splits in two

**Measured**: `EvalCase` is a frozen dataclass (`id/suite/prompt/expected/recorded/events`);
`parse_cases` already refuses estate cases with empty `events`, loudly, at load. The fixture
loader (`load_estate_records`) computes id→hash and holds the records with their `event_type`s.

**Decision**: `EvalCase.asker_role: str = ""`. `parse_cases` validates what the case file alone
can prove: an estate case MUST declare a role, and the role must be in the platform's vocabulary
(`ROLE_VISIBILITY`'s keys — imported, not copied). The **visibility check** — every expected
reference resolvable by the declared role — needs the fixture too, so it lives beside the scorer
and runs at scorer construction: an operator case expecting an authority record is
`UnrunnableSuite`, naming the case and the invisible type. Both checks are refusals, never
defaults — the same discipline `events` already has, for the same reason: a defaulted role would
be the implicit assumption this feature exists to remove, re-established one field over.

## F3 — Which cases get which role, measured not chosen

Per the fixture types and `ROLE_VISIBILITY`:

| Case | Needs | Role |
| --- | --- | --- |
| vault 001 denied | `authority_denied` | compliance-analyst |
| vault 002 nightly apply | run/tool + `authority_denied` (rec-002 in `events`) | compliance-analyst |
| vault 003 granted | `authority_issued` | compliance-analyst |
| vault 004 stopped | `run_stopped` | **operator** |
| vault 005 reads denied | `authority_denied` | compliance-analyst |
| terraform: denied ×2 | `authority_denied` | compliance-analyst |
| terraform: changed / resumed / staging-plan | run/effect types | **operator** |

**A finding inside the finding**: vault-002 — *"What happened during the nightly apply?"* — expects
rec-001, rec-002, rec-003, and rec-002 is `authority_denied`. So **four of five** vault cases are
compliance-analyst cases, not three: an operator asking the same question would receive a faithful
answer resting on two records, which is a *different case* (different expected set), not the same
case with fewer references. The tagging follows the expected set, and the operator-side story for
the nightly apply is a candidate new case, not a retag.

## F4 — Why the naive mutation check is vacuous, and what to assert instead

Correctly tagged cases pass with narrowing **and without it** — each case's expected records are
visible to its declared role, so removing the filter changes nothing the verdict can see. Two
directions that do bite:

1. **Provider input**: an operator-declared case must never hand the provider a record outside
   operator visibility. Observed at a recording provider; deleting the narrowing fails this row.
2. **Load-time refusal**: an operator case expecting an authority reference must refuse to load.
   Deleting the visibility check fails this row.

Both are rows; the contract records the vacuous form so nobody "strengthens" the suite with it.

## F5 — What stays unscored, written where the suite is read

The governed read and its access record, temporal window resolution, and the per-type bound
(which a five-record fixture could not exercise at any depth). Stated in the scorer's docstring,
the `estate_state.toml` headers, and the contract — because an unstated gap of exactly this kind
is what produced this feature.

## F6 — ADR-0059: what a cell's estate evidence asserts

**Measured**: the matrix schema (`_parse_cell`) has `pack/model/role/qualified_by/judge/withdrawn`;
`role` is the **agent** role. Adding an asker-visibility column would change a sealed-ish registry
record and fragment the cell's identity.

**Decision** (the shape the ADR argues; the ADR itself is an implement task): the matrix schema is
untouched. A cell's estate evidence **spans the asker roles its cases declare**, and qualification
requires **every declared role's subset to pass**. The cell's claim becomes: *demonstrated for the
`ask` role, across the asker visibilities the suite names* — precise, recorded in the ADR and the
suite, and requiring no new matrix dimension. Rejected: a per-visibility cell (combinatorial, and
an ask serves whichever role asks); recording visibility in `judge` (a lie of position).

## F7 — US3's re-examination is a live-lane re-run, and the hermetic gate goes first

**Measured**: the blocking gate scores estate via `FixtureScorer`-style recorded providers
(hermetic); the two live cells came from `make evals-live` (~24 min, vendor cost, named runner).
The corrected narrowing lands in both automatically because both go through
`EstateAnsweringScorer`.

**Decision**: hermetic gate green first (it must be — tagged cases, narrowed records, same
verdicts); then the live re-run under the corrected suite decides confirm/re-earn/withdraw, and
the outcome lands in the matrix variables with a comment. FR-010's consequence is pre-stated in
quickstart: withdrawal unbinds the deployed ask until an operator rebinds.

## Open for tasks, not for plan

- Whether vault gains an operator-side nightly-apply case (F3's candidate) now or is recorded as
  a follow-up.
- The exact wording of the suite-header statement of unscored path pieces.
