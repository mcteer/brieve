# Quickstart: reproducing and validating 053

**Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

Every claim this feature rests on is hermetic and cheap. If you doubt one, re-derive it — do
not take the spec's word.

## Prerequisites

```bash
uv sync --all-extras     # NOT --extra <one>, which REPLACES installed extras
```

Only the eval-lane rows (E1–E3) need the enclave (`make dev-up`) and the eval broker.

## 1. Reproduce the finding that produced this feature

**Prose share of the vendored guide** — the 64-of-314 claim:

```bash
python3 - <<'PY'
import pathlib
t = pathlib.Path("packs/terraform/skills/terraform-style-guide/SKILL.md").read_text().splitlines()
fenced = False; prose = 0
for line in t:
    if line.startswith("```"): fenced = not fenced; continue
    if not fenced and line.strip() and not line.startswith("#"): prose += 1
print(f"{prose} prose lines of {len(t)}")
PY
```

**Every "tag" occurrence is inside a fenced block** — the reason SC-002's tagging arm was
invalid:

```bash
grep -n -i "tag" packs/terraform/skills/terraform-style-guide/SKILL.md
grep -n '^```' packs/terraform/skills/terraform-style-guide/SKILL.md
```

Compare the line numbers. Every `tag` line falls inside a fence pair. There is no prose
instruction to tag anywhere in the guide.

**The 16-of-16 overlap**: run the enforcement row (§3) — it is
the same comparison, which is the point. A measurement that only a throwaway script can make is
a measurement nobody will make again.

## 1a. Confirm which packs actually bind a skill

The whole scope rests on this, and an earlier draft of the spec got it wrong:

```bash
grep -n "^phases" packs/*/pack.toml
```

Only the two `packs/terraform` entries appear. `packs/vault`'s skill is pinned and bound to
**nothing** — deliberately, per 051's R12 — so its cards have no bound skill to delegate to and
are not edited by this feature. Row A5 exists because zero restated rules there means *no
binding*, not compliance.

## 2. Confirm the assumption delegation rests on

Delegation is only safe because absent delivery refuses. Verify rather than trust:

```bash
grep -n "skill_missing\|skill_empty\|digest_mismatch" src/core/packs/loader.py
grep -n -B3 "reason_code=\"skill_missing\"" src/core/packs/loader.py | grep raise
```

Each must be reached by `raise ManifestError`. If any becomes a warning, this feature's
premise is gone and row A8 is what will say so.

## 3. Run the hermetic gate rows

```bash
uv run pytest tests/conformance/packs/test_cards_delegate_to_skills.py -v
```

Expected: A1–A9 pass. In particular A4 must demonstrate that the row **fails** against the
pre-feature card text, A5a that it **passes** after the edits, and A5 that `packs/vault` is
reported *unbound* rather than clean. A run where
A1 passes but A4 does not is a detector that finds nothing.

Whole hermetic suite:

```bash
make check
```

## 4. Re-measure SC-002 (eval lane, named runner)

```bash
make dev-up
uv run python evals/prompt-tune/sc002_skill_effect.py -n 5
```

**Read the result the way the harness tells you to.** A level result is a finding about the
rule and the model, not a failure of the harness. Do not lower the threshold, and do not go
looking for a fourth rule that scores better — record the finding and amend 051's SC-002
(SC-004). This feature exists because the first null result was read as a question about
measurement when it was a question about the content.

## 5. Re-qualify before promoting

Card edits change the instruction that was qualified. Promotion is all-five-or-none:

```bash
make conformance
# plus the phase-agent qualification suites over ASSEMBLED content
```

A card edit may not ship on the strength of the eval that qualified the previous text
(FR-010, [R8](research.md)).

## What "done" looks like

- `make check` green, with A4 and A5 demonstrating the row can both catch and be satisfied
- Three terraform cards shorter, each delegated rule gone; **no vault card edited**
- §Pins retained and **saying what it overrides and why**
- 051's SC-002 contract amended with the withdrawal and the selection error
- SC-002 either met on a stated rule, or recorded as unmeetable with the measurement
- `git diff --stat src/` empty
