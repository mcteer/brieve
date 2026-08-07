# Implementation Plan: Customer-supplied context — endorsed, pinned, and citable

**Branch**: `spec/045-customer-endorsed-context` | **Date**: 2026-08-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/045-customer-endorsed-context/spec.md`, measured
against `d6be271` plus this branch.

## Summary

A customer's own documents become citable the way the platform's corpus is citable — synced,
pinned, verified on read — with the trust statement supplied by a recorded endorsement instead
of by the supply chain. The platform detects upstream drift and notifies; an administrator
reviews what changed and adopts it; a run in flight keeps the ground it started on, across
interruption and resume. Every citation carries its provenance as data, and an answer resting
on customer material says so.

**The design in one sentence** (research R1): a second, parallel corpus behind the same
resolution contract — never a tenant dimension threaded through the pinned reader — so the
gate this feature is most likely to weaken is not edited at all.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed), matching the tree

**Primary Dependencies**: none added. Sync reuses the corpus-sync extraction approach in
platform code; detection lists remote refs without cloning; the console rides 044's
`ConfigChange` unchanged

**Storage**: governance facts in the trust fabric (`endorsed-sources`, the fourth console
record); content in the harness Postgres as immutable content-addressed versions
(`candidate` / `adopted` / `superseded`), superseded versions retained because runs may pin
them (R3/R4)

**Testing**: pytest — unit + hermetic conformance (E1–E24); `enclave`-marked EL1–EL2
fail-not-skip; the a11y lane walks the new page (EL3). Named runner: Dan

**Target Platform**: the enclave; API + portal + the persistent MCP service (detection probe)

**Project Type**: single project — additions in `src/core/answering` (the endorsed reader and
combined view, beside the pinned reader, not inside it), `src/surfaces/{api,portal,mcp}`,
`infra/modules/trust-fabric`

**Performance Goals**: resolution stays a dictionary lookup; detection is one refs listing per
endorsed source per checker cycle; zero outbound requests during answering (E23, instrumented)

**Constraints**: sync-then-answer, never fetch-at-answer; detect ≠ adopt; one content identity
per run record; the pinned corpus untouched (US6 by construction)

**Scale/Scope**: 1 new corpus reader + combined view, 1 console record (four places + scan),
1 health-checker probe, 1 sync/review module, ~24 conformance rows, ADR-0070

## Constitution Check

*Named-runner obligation*: EL1–EL2 and the enclave rows have no automated runner. **Dan runs
them before merge**; the contract records this.

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Git is the content transport (adopted CLI posture, ADR-0066's spirit); no parser or diff engine beyond section extraction the corpus-sync already does; the fabric decides endorsements |
| II — Total Interception; One Governed Tool Layer | **Pass with an ADR** | Sync/detection is non-tool egress from a served process, which the enumerated classes do not cover — **ADR-0070 adds the class with its bounds** (R6): endorsed sources only, never during answering (E23), read-only. Portal-only console surface per 044's posture; no MCP verb |
| III — Fail-Closed, In-Process Enforcement | **Pass** | Digest mismatch refuses like `CorpusUnavailable` (E7); a withdrawn source resolves nothing; sync failure never degrades to answering from unverified content; three distinct failure reports (E8) |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | Endorsing/adopting are administrator acts through the gated path; a dispatched run cannot reach any of it (E24, rigged-on construction); private-source credentials are trust-store material referenced per sync, never entered (E10) |
| V — Sealed Core, Versioned Seams | **Pass** | The pinned reader is not edited; the endorsed reader is a second implementation of the same contract; the run record gains one bounded field beside `corpus_digest`; checkpoint pinning uses the blob's existing payload dict |
| VI — Lean by Default | **Pass** | No new operated component: content in the existing Postgres, detection in the existing health checker, governance in the existing fabric + console |
| VII — Anti-Fragmentation | **Pass** | The platform corpus stays identical everywhere; customer content is per-deployment *data*, not a per-deployment code path |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | No model, prompt, or pack is promoted; ADR-0030's pinned-vs-consulted tension is resolved in ADR-0070 rather than silently contradicted — customer content is consulted material handled by the pinned mechanism, ADR-0021's labelled-snapshot shape |
| IX — Evidence Over Claims | **Pass** | Endorsement, sync, drift, adoption, withdrawal — all recorded with who and when; provenance is per-citation **data**; one content identity per run record (E17); the age of the ground is disclosed by the existing rule |
| X — The Decision Record Governs | **Pass** | ADR-0070 (new, Proposed); ADR-0004/0021/0030/0046/0069 consumed, none silently contradicted |

**Gate result**: **PASS — proceed** (re-checked post-design; the Principle II note is the one
conditional, and ADR-0070 is in scope, not deferred)

## Project Structure

### Documentation (this feature)

```text
specs/045-customer-endorsed-context/
├── plan.md              # This file
├── research.md          # R1–R10
├── data-model.md        # EndorsedSource, SyncedVersion, EndorsedCorpus, DriftFlag, run pinning
├── quickstart.md        # Hermetic → endorse-and-cite → drift/review/adopt
├── contracts/
│   └── conformance-endorsed-context.md   # E1–E24, EL1–EL3, named runner
└── tasks.md             # /speckit-tasks output (not created here)
```

### Source Code (repository root)

```text
src/
├── core/answering/
│   ├── endorsed.py            # NEW: EndorsedCorpus + load_endorsed + the combined view (R1)
│   └── corpus.py              # UNTOUCHED — US6 by construction
├── core/durability/           # checkpoint payload carries the version pin (R4; no schema change)
├── surfaces/
│   ├── api/
│   │   ├── console.py         # +endorsed-sources record parser, review/adopt routes
│   │   ├── authority_submit.py  # CONSOLE_RECORDS + endorsed-sources
│   │   └── ask.py             # combined view resolved once per request; provenance on citations
│   ├── mcp/
│   │   ├── transport.py       # same combined view (ADR-0033 parity)
│   │   └── health.py          # +drift probe (R5)
│   ├── portal/templates/      # settings.html gains the endorsed-sources section + review page
│   └── sync/endorsed_sync.py  # NEW: clone/extract/version into Postgres; candidate on review

infra/modules/trust-fabric/
├── authority-submit.tf        # +endorsed-sources grant
├── control-groups.tf          # console_controlled_paths += endorsed-sources
└── policies.tf                # harness_authority_read += exact path (042's lesson, third use)

tests/
├── unit/                      # parsers, version arithmetic, the four-place scan extension
├── conformance/endorsed/      # NEW: E1–E24 (E22's diff row; E23's instrumentation)
└── a11y/                      # EL3

docs/adr/0070-endorsed-content-sync-is-an-egress-class.md
```

**Structure Decision**: single project. The one deliberate asymmetry mirrors R1: everything
endorsed lives *beside* the pinned machinery, never inside it — `endorsed.py` beside
`corpus.py`, a second reader behind the same contract — so US6's "nothing weakened" is a
property of what was not edited rather than a discipline about how it was.

## Complexity Tracking

No Constitution Check violations. Two judgment calls, recorded:

| Call | Why |
| --- | --- |
| Superseded versions retained indefinitely | A version is unreferencable only when no run record cites it and no suspended run pins it — deletion is a decision with a query behind it, not a TTL. Deferred with its reasoning (R3), the 040 kept-requests shape |
| Detection rides the health checker rather than a schedule of its own | The checker is the platform's existing ambient loop; a second periodic mechanism would be Principle VI's thousand-optional-dependencies death by another name. The cost — drift is noticed at the checker's cadence, not instantly — is acceptable for content that changes on human timescales |
