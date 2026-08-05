# Data Model: The agent authors, and a person merges

**Feature**: 038 | **Date**: 2026-08-05

Entities from the spec, with the fields, rules and transitions the design needs. Where a
choice could reasonably have gone another way, the reason is here rather than in a commit
message.

---

## The two trees, and why they are two

Every containment property in this feature comes from one decision, so it is stated first.

| Tree | Mount | Contains | Written by |
| --- | --- | --- | --- |
| **Subject** | read-only | the requester's repository | nobody — the mount forbids it |
| **Workspace** | read-write | only what the agent authored | `author_file`, and nothing else |
| *(the platform's own tree)* | **absent** | — | — |

**The proposal is built from the workspace and never from the subject.** That single sentence
is what FR-013a asks for: a file the agent did not write has no route into the proposal,
because the code that builds the proposal never reads the subject except to compute a diff for
a path the agent *did* write.

**`§ Containment` below splits into two functions for this reason**, and the split is
load-bearing rather than tidy: the file half is structural and the prose half is inspected. A
single `check_containment()` would let a reader assume the strong guarantee covers both.

---

## Isolation tier (extended — `core/isolation/tier.py`, moved from `core/intake/`)

037's `TierPosture` with one field added. **`repo_mounted` is unchanged in name and meaning:
the platform's own repository.** That is already what 037's jobspec comment says it guards
against — *"a mount would hand a redirected analyzer the whole tree to read and the packs to
write."*

| Field | Type | Rule |
| --- | --- | --- |
| `network_mode` | `str` | must be `bridge`; `host` fails (unchanged) |
| `egress_allowlist` | `frozenset[str]` | **static configuration**, never per-run (FR-005a) |
| `repo_mounted` | `bool` | the **platform's** tree; must be `False` (unchanged) |
| `subject_mount` | `SubjectMount \| None` | **new.** `None` passes (037's payload delivery); present-and-writable **fails** |

```
SubjectMount: path: str, read_only: bool
```

**`is_hardened()` gains exactly one clause** — a writable subject mount fails, naming which
clause failed as every other one does. 037's merge-blocking row
(`test_isolation_tier.py:79`) passes `repo_mounted=True` and still fails, unchanged; the new
field defaults to `None` so every existing caller is untouched.

**Why not relax `repo_mounted` instead**: the jobspec predicted its own weakening — *"the
clause most likely to be 'temporarily' added back for convenience"* — and a feature that
relaxed it would have been that prediction coming true. Adding a narrower field keeps the
original property assertable and makes the new one assertable beside it.

---

## Authoring request

What a person asked for, and where it may land.

| Field | Type | Rule |
| --- | --- | --- |
| `correlation_id` | `str` | the run's, as everywhere else |
| `requester` | subject identity | whose repositories are in scope |
| `target_repository` | `str` | **must be one the requester owns** — refused *before anything is produced* (FR-007) |
| `task` | `str` | what to author |
| `pack` | `str` | must declare an authoring workflow; `terraform` today, and nothing else |

**Ownership is enforced at the credential, not only at the check.** The publishing
credential is installation-scoped to the requester's own repositories (R9), so a request
naming somewhere else fails twice: once at the check, and once because the token could not
reach it. FR-007 asks for the first; the second is what makes the first hard to regress.

**This is a dispatch payload, not a northbound operation** (R16). An authoring request reaches
the platform as an ordinary dispatched run whose definition carries `author_file` — so Principle
II's surface parity is **inherited rather than owed**, and a row asserts no new northbound verb
was added. An absent parity row and a deliberately-inherited one look identical in a diff, and
only one of them is a gate regression.

---

## Authored artifact

What the agent produced. **Paths and digests here; content lives in the workspace and then in
the proposal.**

| Field | Type | Rule |
| --- | --- | --- |
| `paths` | `tuple[str, ...]` | every path `author_file` wrote, in write order |
| `digests` | `dict[str, str]` | sha256 per path |
| `created` / `edited` | `frozenset[str]` | partition of `paths`; a path is `edited` iff it exists in the subject |
| `truncated` | `bool` | the subject was not read in full |
| `truncation_note` | `str` | required non-empty when `truncated` — **disclosed in the proposal** (FR-005b) |

**No content field, deliberately.** `ARTIFACT_AUTHORED` carries paths and digests only. The
artefact is a derivative of a private repository, and an append-only trail holding a verbatim
copy puts it somewhere nobody can delete it. `PROGRAM_SUBMITTED`'s verbatim rule does not
transfer: that member records *the model's own words as the cause*, which is `TURN_RECORDED`'s
case; this records a derivative of *someone else's private code*, which is not.

**Empty is a legitimate outcome** (spec edge case). An artefact with no paths is distinguishable
from a failure: the run completed, the artefact is empty, and the proposal says so rather than
nothing being produced.

---

## Containment — two rules, two mechanisms

### Files (structural)

Nothing to check. The proposal's file set **is** `artifact.paths`; the diff for an `edited`
path is computed between the subject's copy and the workspace's copy.

**FR-013b holds for free.** A diff of an edited file carries surrounding context because that
is what a diff is — there is no rule that could refuse it, so there is none to get wrong.

### Prose (inspected)

Commit messages, proposal title and body. Composed from **structured fields** (task, files
touched, disclosures, limits) with **one free-text rationale field**, and that field is
scanned before the proposal is emitted.

| Check | Fires on | Result |
| --- | --- | --- |
| Verbatim span | a span of ≥ N characters matching a subject file **not** in `artifact.paths` | `CONTAINMENT_REFUSED`, code `analysed_content_in_prose` |
| Secret value | a value matching the secret-detection set anywhere in files, commits or prose | `CONTAINMENT_REFUSED`, code `secret_value_in_output` |

**Why prose is the weaker half, said plainly**: a determined paraphrase defeats a verbatim
scan. This is the residual risk, and it is bounded by the structured composition — the free
field is one field, not the whole body — rather than eliminated. Stating it here means nobody
later reads "containment is structural" as covering the description, which is exactly the
mistake FR-013 was written to prevent.

**The refusal record carries codes, locations and digests — never the matched text.**
`CANARY_CONTACT`'s rule, for its reason: the record of a leak must not be a second copy of
what leaked.

---

## Proposal

The only way work leaves the platform.

| Field | Type | Rule |
| --- | --- | --- |
| `target_repository` | `str` | the requester's |
| `branch` | `str` | derived from the correlation ID — **never reused** (FR-009) |
| `files` | created content + diffs of edited | from the workspace, structurally |
| `body` | structured sections + one rationale field | inspected before emission |
| `disclosures` | `tuple[str, ...]` | truncation, empty artefact, anything the reader would otherwise assume away |
| `limits` | `str` | unconditional, last — 037's `_NO_CHECKS_NOTE` precedent |

**States**: `composed → refused` (containment) or `composed → opened → {merged, closed}`.
The platform writes the first three. **`merged` is written by observing the host, never by the
platform acting** — and a proposal that is never reviewed stays `opened` and is reported as
`opened`, not as complete (spec edge case).

**A limits statement, unconditionally.** 037's R10 finding transfers exactly: a reviewer
handed a clean proposal reads "clean" as "correct" unless the artefact says otherwise, and the
failure this feature is most likely to cause is a review that has been reassured rather than
informed. Here the limits are specific — what was analysed, what was truncated, that two
correctness gates ran and what each said.

**And one limit that is not a caveat but a structural fact**, from the spec's own edge cases:
*an authored artefact necessarily reflects what was read.* Where the analysed source is itself
the sensitive thing — a proprietary algorithm, an undisclosed schema — "carry nothing out" is
**not achievable by containment**, because the integration the requester asked for is a
derivative of exactly that. The containment rules bound what is *copied*; they cannot bound what
is *implied*. The limits statement says so in the artefact, because the alternative is a
guarantee the feature cannot keep being read as one it can, and a reviewer deciding what to
publish needs that distinction before they merge rather than after.

---

## Provenance record

FR-020b: the platform must tell its own output from a person's, **at the moment of enactment**.

| Field | Type | Rule |
| --- | --- | --- |
| `content_digest` | `str` | sha256 of an authored file |
| `correlation_id` | `str` | the run that authored it |
| `proposal_state` | enum | as above |

**Two layers, and the second is not redundant** (R11):

1. **Structural** — the authoring definition's ceiling contains no enacting tool; the
   proposing step's ceiling contains no authoring tool. SC-009 is asserted against this.
2. **Provenance** — enactment consults the record and refuses `ENACTMENT_REFUSED` on
   platform-authored content with no recorded human merge.

The structural layer is a fact about *today's definitions*. The provenance layer is what
survives a definition somebody writes next year, which is what "checkable at the moment of
enactment, not inferred later" asks for.

**`terraform_apply` is not modified.** Once a person merges, the artefact is ordinary reviewed
configuration and the provenance record says so — applying it is the act it always was
(FR-020a).

---

## Write cell and its corpus

The matrix's third role, unbound until now. `QualifiedCell(pack, model, role="write", ...)`
— no schema change; `validate_binding_map` already refuses a definition binding `write` to a
cell qualified for something else, and its error message already uses a `write` cell as its
worked example.

### Corpus shape (`evals/authoring/`)

**Not in `SUITES`** (R7). `SUITES` is the per-pack list, and membership would demand
`packs/vault/evals/integration_correctness.toml` for a capability the Vault pack does not
offer — 037's exact mistake, caught by the same rule (*a gate with no cases must fail rather
than pass vacuously*). Instead: `AUTHORING_QUALIFICATION`, **required of a pack that declares
an authoring workflow and not asked of one that does not.**

| Case kind | Carries | Scored by |
| --- | --- | --- |
| **Golden task** | prompt, product tooling invocation, **human-authored reference** | both gates, separately |
| **Must-deny** | a subject seeded with a secret / unrelated content / instructions to the agent | the artefact, not a verb |

**Floor — fails, never warns** (FR-018b), on `intake_seed`'s mechanism:

- at least one golden task that is **syntactically valid and substantively wrong** in its
  reference comparison — a corpus that only catches malformed output has not measured
  integration correctness (SC-008);
- must-deny coverage across all three classes FR-017 names (secrets in output, exfiltration of
  analysed content, injection resistance);
- **every golden task carries a human-authored reference** (FR-018c) — a task without one
  cannot participate in the second gate, so it is refused rather than silently scored on one.

**The clause most likely to erode** is the last one, and it erodes by generating references.
That measures the generator against itself and passes. The corpus format therefore records
each reference's **author** as a required field, so "human-authored" is a claim in the
artefact rather than an intention in a review.

### The two gates, reported separately (FR-018a)

| Gate | Catches | Runs |
| --- | --- | --- |
| **Product tooling** | malformed — does it parse, do the types line up | CI, with the binary and a pinned provider mirror (R10) |
| **Reference comparison** | **subtly wrong** — a static credential where dynamic secrets were asked for | alongside |

Reported as two numbers. Collapsing them hides which occurred, and *which occurred* is the
whole distinction ADR-0038 warned about.

**If the tooling gate cannot run, it fails.** Never a silent degradation to `fmt`-only while
still reporting "validated" — that is ADR-0047's passing stub in the costume it would wear here.

---

## Audit vocabulary (additive — Principle V review)

| Member | Payload | The rule that matters |
| --- | --- | --- |
| `ARTIFACT_AUTHORED` | paths, per-path digests, created/edited, truncated | **Digests, never content.** A derivative of private code does not belong in an append-only store |
| `PROPOSAL_OPENED` | repository, branch, artefact digest, proposal reference | The platform's act. **A merge is not here** — it is observed, and a reader must never mistake one for the other (FR-008) |
| `CONTAINMENT_REFUSED` | code, location, digest | **Codes and digests, never the matched text.** `CANARY_CONTACT`'s rule |
| `ENACTMENT_REFUSED` | content digest, authoring correlation ID, attempted tool | The provenance rule firing. Distinct from an ordinary `PRE_DECISION` denial because *whose output it was* is the reason |

Four additive members on `TOOL_CHOSEN`'s precedent and 037's four. `test_widening_the_event_vocabulary_moves_no_existing_hash`
pins the existing digests and must stay green.
