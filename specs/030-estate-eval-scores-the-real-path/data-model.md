# Data model: 030 — the estate eval scores the real path

**Phase 1.** One field, one check, role tags on data, one decision record. Nothing persisted
beyond the TOML the packs already hold.

---

## The estate case (one additive field)

| Field | Rule |
| --- | --- |
| existing fields | unchanged |
| `asker_role` **(new)** | **Required for estate cases**, refused at parse when absent or outside the platform's role vocabulary (`ROLE_VISIBILITY`'s keys, imported). Ignored for every other suite. Never defaulted — a defaulted role is the implicit assumption this feature removes, one field over |

## The visibility check (at scorer construction, where cases and fixture meet)

| Property | Rule |
| --- | --- |
| Input | The suite's cases + the fixture estate (which knows each record's type) |
| Rule | Every id in a case's `events` must be a type the case's `asker_role` may see |
| On violation | `UnrunnableSuite`, naming the case, the reference and the invisible type — a refusal, never an exclusion-by-silence |

## The narrowing (in the scorer, per case)

| Step | Rule |
| --- | --- |
| 1 | `visible = visible_event_types({case.asker_role})` — the platform's own function, no second table |
| 2 | Records handed to `answer_estate_question` are the fixture's ∩ visible |
| 3 | Empty result is impossible for a loadable case (the visibility check above guarantees the expected records survive) — asserted, not assumed |

## The role tags (measured in research F3)

Vault: 001/002/003/005 → `compliance-analyst` (002 expects an authority record among its three),
004 → `operator`. Terraform: the two denied-cases → `compliance-analyst`, the other three →
`operator`. The tag follows the **expected set**, not the prompt's vibe.

## ADR-0059 (the meaning, not the schema)

| Decided | Value |
| --- | --- |
| Matrix schema | Untouched — `role` stays the agent role |
| A cell's estate evidence | Spans the asker roles its cases declare; qualification requires every declared role's subset to pass |
| Rejected | Per-visibility cells (combinatorial); visibility smuggled into `judge` |

## What deliberately does not change

- `run_suite`'s estate scoring (precision/recall over surviving references) — the verdicts are
  computed as today, over narrowed inputs.
- The matrix records, the ask binding, the deployed surfaces.
- Role visibility itself (FR-011).
