# Implementation Plan: The corpus refresh — answers that can say how old their ground is

**Branch**: `spec/033-corpus-refresh` | **Date**: 2026-08-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/033-corpus-refresh/spec.md`

## Summary

Three moves, dependency-ordered. The pin learns *when* (manifest gains `synced_at`, written by
`corpus-sync`; the loader exposes it and treats absence as unknown). Answers learn to *say so*
(a platform-composed `ground_note` on the guidance `Answer`, mirroring 029's `window_note`
exactly — same composition point, same surface plumbing, never an audit payload; 30/90-day
tier wording, unknown as its own wording, decline never). And the refresh learns to *happen*
(a weekly scheduled workflow runs the corpus sync and the vendored-skills check, and opens a
reviewable PR even when only the timestamp moved — landing stays Dan's act). The vendored
skills' provenance already exists as the loader-parsed `[upstream]` pin (analyze C1); the
helper consumes it and moves only `retrieved`, and the vault skill — authored here,
upstream-bound — is refused by the manifest's own `provenance = "authored"` field.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed), Bash for the sync orchestration, GitHub
Actions YAML for the schedule

**Primary Dependencies**: stdlib only for the sync (urllib, html.parser — settled in 024);
`gh` CLI in the scheduled workflow for the PR; no new packages

**Storage**: the git repository itself — `corpus/manifest.json` + `corpus/documents` and
`packs/*/skills` + `packs/*/pack.toml` are the pins; no database change, no Vault change

**Testing**: pytest — hermetic component rows for the loader/note/tiers; conformance rows for
the full ask path carrying the note on every surface payload; a workflow-shape row that
asserts the schedule's YAML invokes exactly the reviewed scripts (prose-to-code drift is a
known trap here — five prior instances, shared stripper)

**Target Platform**: unchanged (dev enclave + CI)

**Project Type**: existing single project; additive fields on existing seams

**Performance Goals**: none meaningful — the note is a string composed from one timestamp

**Constraints**: merge lanes stay hermetic (the note reads the pin, never the network; the
weekly workflow is the ONLY thing that fetches, and it is not a gate); `Answer` and `Corpus`
are frozen dataclasses — new fields are additive with empty/None defaults so every existing
constructor call stands; no sealed-core audit payload changes (Principle V — the note rides
the answer object, the exact `window_note` precedent)

**Scale/Scope**: ~6 source files touched, 1 new workflow, 1 new sync helper for skills
provenance; the 33-document pin untouched until the first real re-sync lands by review

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | Pass | No framework, no new service; a timestamp, a note, a cron |
| II — Total Interception | N/A | No tool surface changes; answering path only |
| III — Fail-Closed | Pass | Unparseable/absent/future timestamps read as *unknown* and disclosed — never a crash, never silently fresh |
| IV — Zero Standing Credentials | Pass | The workflow uses the repo's own CI identity to open a PR; no new secret, no vendor call |
| V — Sealed Core, Versioned Seams | Pass | `ground_note` on the Answer object (window_note precedent); zero audit payload changes; `Corpus`/`Answer` gain optional fields on their existing seam |
| VI — Lean by Default | Pass | Reuses corpus-sync, pack.toml digests, promote_skill's bump lens; adds no parallel mechanism |
| VII — Anti-Fragmentation | Pass | One note composer serves all three surfaces through the shared payload; tier constants live in one place |
| VIII — Eval-Gated Promotion | Pass | A skills content change arrives as a digest bump through the existing promotion/injection lens; the schedule proposes, review lands — pinned-vs-fresh is exactly what this feature strengthens |
| IX — Evidence Over Claims | Pass | "We checked at T" becomes a reviewed commit, not a log line; the disclosure makes the answer's currency claim explicit |
| X — Decision Record Governs | Pass | ADR-0004 consumed; no new ADR — the spec's Traceability row says so and analyze holds it to that |

**Gate result**: PASS — proceed.

## Project Structure

### Documentation (this feature)

```text
specs/033-corpus-refresh/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions F1–F8
├── data-model.md        # Phase 1 — the pin, the note, the provenance record
├── quickstart.md        # Phase 1 — validation scenarios
├── contracts/
│   └── conformance.md   # Who runs what, and what each row asserts
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
corpus/manifest.json                       # gains "synced_at" (written by sync, optional on read)
infra/bin/corpus_sync.py                   # writes synced_at; mechanics otherwise untouched
infra/bin/skills-provenance                # NEW: checks adopted packs' existing [upstream] pin against
                                           #   upstream HEAD; updates only `retrieved`; refuses authored packs
src/core/answering/corpus.py               # Corpus.synced_at (None default); loader parses/refuses-to-crash
src/core/answering/ground.py               # NEW: describe_ground(synced_at, now) → the tiered note; the
                                           #   30/90-day constants live here and only here
src/core/answering/answer.py               # Answer.ground_note: str = "" (additive, frozen-safe)
src/surfaces/api/ask.py                    # ask_for GAINS `now: datetime | None = None` (estate already has
                                           #   it; guidance does not — analyze A2); composes + serializes note
src/surfaces/portal/templates/ask.html     # renders ground_note beside the existing window_note block
packs/terraform/pack.toml                  # [upstream].retrieved moves on check — NO new fields (analyze C1)
.github/workflows/corpus-refresh.yml       # NEW: weekly cron + manual dispatch → sync both → open PR
tests/component/test_ground_note.py        # NEW: tiers, unknown, future-time, absent-manifest rows
tests/conformance/answering/…              # the full-path row: every guidance answer carries the note
```

**Structure Decision**: additive fields on the two existing seams (`Corpus`, `Answer`), one
new pure function module for the note, one new workflow. The MCP surface needs no change —
its `ask` op proxies the API payload, so the note arrives there the day the API serializes
it, and a conformance row asserts that rather than assuming it.

## Dependency order

US2 (the pin records when) → US1 (the answer discloses) → US3 (the schedule proposes).
US2 and US1 are hermetic and land together as the feature's core; US3 is CI-side and
verifiable by manual dispatch before its first scheduled firing.

## Complexity Tracking

No violations to justify.
