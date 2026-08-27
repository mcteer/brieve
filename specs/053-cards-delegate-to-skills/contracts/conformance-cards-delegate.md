# Conformance contract: a phase card delegates to the skill it is bound to

**Feature**: 053 | **Date**: 2026-08-27 | **Spec**: [../spec.md](../spec.md)

Gate rows attach as the feature lands (ADR-0047). A row that cannot fail is worse than a row
that is missing, so every row below names the state in which it fails.

## 1. Hermetic rows — `tests/conformance/packs/`

| Row | Asserts | Fails when | FR / SC |
| --- | --- | --- | --- |
| A0 | The per-card baselines are the **derived** ones, sharing a denominator across all four cards | a probe count is used as a target — the defect analyze caught in T003 | FR-003 |
| A1 | No card states a rule its bound skill states, except a declared override | any of the 16 terraform rules returns to `write`, or the 7 to `judge`, or the 6 to `plan` | FR-001, SC-001 |
| A2 | An override is recognised from the card's own text, with its reason | §Pins keeps its rule but stops saying what it overrides | FR-002 |
| A3 | Content inside a fenced code block is never counted as a stated rule | the inventory admits `default_tags`, `validation` or aliased providers as taught practice | FR-003 |
| A4 | The row fails against the terraform pack's **pre-feature** card text | the detection is too weak to have caught what this feature was written for | FR-007, SC-003 |
| A5 | `packs/vault` is reported **unbound**, not clean — its skill is bound to no phase | zero-restated-for-want-of-a-binding becomes indistinguishable from zero-restated-because-the-card-delegates | **FR-007a**, SC-003 |
| A5a | The terraform pack passes **after** the edits | the positive half of A4; without it A4 alone shows only that something is wrong | FR-007, SC-003 |
| A6 | The inventory's digest matches the manifest's pinned digest | `SKILL.md` is re-pinned and the inventory is left describing bytes that are gone | **FR-012** |
| A7 | Every phase bound to a skill is compared, not a hard-coded three | a fourth phase is bound later and is never checked | FR-005 |
| A8 | Delegation is safe: absent delivery refuses | `skill_missing`, `skill_empty` or `digest_mismatch` stops raising, so a delegating card could run without what it delegated | FR-001 |
| A9 | The pack-level total is reported, not only per-card | the practice is distributed across cards and each card reads clean ([R2](../research.md)) | FR-005 |

**A4 and A5a are the pair that makes A1 evidence.** A1 alone would pass against a detector that
finds nothing. A4 pins that it caught the real defect; A5a pins that the rule is satisfiable.
Terraform is both halves of that control — failing before the edits, passing after.

**A5 is a different guard, and analysis is what found it.** An earlier draft made "the row
passes against `packs/vault`" the control. It would have passed by asserting nothing:
`packs/vault/pack.toml` has no `phases` key, so its cards have no bound skill, FR-001 is
vacuous there, and zero restated rules means *no binding* rather than *good delegation*. A5
now asserts the gate can tell those apart — which is the hazard the mistake exposed, kept as a
row instead of quietly dropped.

**A8 is the load-bearing row.** Delegation removes rules from a card on the strength of them
arriving from elsewhere. If that ever stops being enforced, this feature converts a duplicated
rule into a missing one, silently, and nothing else here would notice.

## 2. Eval-lane rows — named runner

| Row | Asserts | Named runner |
| --- | --- | --- |
| E1 | The three edited terraform phases re-qualify before promotion, all-five-or-none | Dan — eval lane, FR-010, SC-005 |
| E2 | **051's SC-002, re-measured** on a rule selected from *stated* instruction, bound vs unbound, n>=5 per arm | Dan — `evals/prompt-tune/sc002_skill_effect.py` |
| E3 | No regression on the existing corpus: `no_floating_version_constraint` does not fall, since §Pins is retained as an override | Dan — eval lane |

**Named runner**: Dan McTeer (maintainer). Rows fail loudly when the enclave or eval broker is
absent — do not skip green.

### What E2 may return, and what may not be done about it

*Throughout this section **SC-002 means 051's** — 053 has its own SC-002, which is a claim
about the instruction rather than the authored output.*

E2 has **two** acceptable outcomes and the feature is complete on either:

1. **Demonstrated.** The rule is followed with the binding and demonstrably less often without.
2. **Not demonstrated, and recorded.** The finding is that this skill has no teachable surface
   for the qualified model, written down with the measurement that establishes it, and 051's
   SC-002 amended to say so (SC-004).

**What may not happen** is a third pass looking for a rule that scores better, or a threshold
that moves. The harness already prints that instruction on a null result. This contract repeats
it because this feature exists *because* the first null result was read as a question about
measurement when it was a question about the content.

**The candidate must be structural** ([R5](../research.md)) — file organisation or declaration
ordering — because it must be unambiguous to detect and stated in prose. The two rules 051
measured were drawn from example code, which is the selection error this feature is fixing.

## 3. Amendments this feature owes to 051

| Owed | Why |
| --- | --- |
| 051 SC-002's contract records the **withdrawal** of the minimality hypothesis | It rested on a false premise: no tagging instruction was ever delivered, so the tagging arm never tested whether the Write card's minimality clause suppresses delivered stylistic guidance (FR-008) |
| 051 SC-002's contract records the **selection error** | Both measured rules were drawn from fenced example code rather than stated instruction, which is the whole explanation for the null result (FR-008) |

Both are corrections to a shipped record and are made in place, with the date and the
measurement — not by quietly restating the original conclusion.

## 4. Stability commitments

- **No core source changes.** SC-006 is asserted, not asserted-by-intention: the row set
  includes a check that `src/` is untouched by this feature's file list.
- **`SKILL.md` is not edited.** It is upstream, digest-pinned to commit `8c6573ab`. Any row
  that would pass by changing it is invalid.
- **051's mechanism is consumed unchanged** — delivery, precedence, refusal codes, and the
  unsatisfiable declarations. This feature adds no runtime behaviour.

## 5. Implementation PR named-runner record

To be filled on `feat/053-cards-delegate-to-skills`.

| Row | Named runner | Status |
| --- | --- | --- |
| E1 | — | pending |
| E2 | — | pending |
| E3 | — | pending |

## 6. Security-maintainer review

**Not required.** This feature touches no sealed-core surface: no registry schema, no audit
payload, no credential or authority path. Pack content and test rows only (Principle V). If
implementation finds it needs a `src/` change, that finding invalidates SC-006 and the review
obligation returns with it.
