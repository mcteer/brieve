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
is what FR-013a asks for **about paths**: a file the agent did not write has no route into the
proposal, because the code that builds the proposal never reads the subject except to compute a
diff for a path the agent *did* write.

**It says nothing about bytes, and an earlier draft of this document claimed otherwise.** An
authored file is agent-controlled content — the agent can write whatever it read into a file it
did create. So containment is **two claims of different strength**, and they are stated
separately because collapsing them is exactly how the second one went missing:

| Claim | Covers | Strength |
| --- | --- | --- |
| **Which paths appear** | the file set | **Structural** — unforgeable; the workspace is the only source |
| **What those paths contain** | authored bytes, diff additions, prose | **Inspected** — the verbatim scan, over the *whole proposal* |

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
| `tenant_id` | `str` | required — `AuditEntry` demands one, and repository ownership is a tenancy question before it is anything else |
| `requester` | subject identity | whose repositories are in scope |
| `target_repository` | `str` | **must be one the requester owns, within their tenant** — refused *before anything is produced* (FR-007) |
| `task` | `str` | what to author |
| `pack` | `str` | must declare an authoring workflow; `terraform` today, and nothing else |

**The ownership check is the SOLE enforcement of requester scope, and an earlier draft
over-claimed here.** A version-control App installation is scoped to the **installing account or
organisation**, not to an individual — so two requesters inside one organisation are inside one
installation, and the credential would happily reach either's repositories. The earlier claim
that a bad target "fails twice" holds only for a single-user installation, which is not the case
that matters.

So the layering is stated accurately rather than reassuringly: **the credential bounds the
installation; the check bounds the requester.** There is no second line of defence on requester
scope, which is precisely why the check is asserted by its own row against a *same-installation,
different-owner* target rather than only against an obviously-foreign one.

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

### Content (inspected — the whole proposal, not only the prose)

Authored file contents, the **added** lines of every diff, commit messages, and the proposal
title and body. The body is composed from **structured fields** (task, files touched,
disclosures, limits) with **one free-text rationale field**; the structure bounds the prose, and
the scan below covers everything.

| Check | Fires on | Result |
| --- | --- | --- |
| Verbatim span | a span **≥ 120 characters spanning ≥ 2 non-blank lines** (whitespace-normalised) matching a subject file **not** in `artifact.paths` | `CONTAINMENT_REFUSED`, code `analysed_content_in_artifact` or `analysed_content_in_prose` |
| Secret value | a value matching the secret-detection set anywhere in files, commits or prose | `CONTAINMENT_REFUSED`, code `secret_value_in_output` |

**Two conditions on the span, because either alone fails.** A character count alone trips on a
long identifier or a URL; a line count alone trips on two short adjacent lines any integration
would reproduce. Together, **no single token, signature or config key can trip the scan**, while
a copied comment block, docstring or function body does. 120 characters is a couple of lines of
real code — an order of magnitude above identifier scale, and below a copied paragraph.

**The legitimate case has its own row**, the C3 treatment applied here: an artefact that reuses
the subject's identifiers, type names and config keys **must not** be refused. That reuse is
what integrating *is*, and a containment check tuned until it stopped complaining would
plausibly have arrived at a rule forbidding it.

**Diff context needs no exemption.** The scan ignores files **in** `artifact.paths`, and an
edited file is in that set by definition — so FR-013b holds without a special case.

**Two reason codes rather than one**, because a leak in the code and a leak in the description
are different mistakes with different fixes, and a reviewer should not have to go looking.

**The residual risk, stated plainly**: a determined **paraphrase** defeats a verbatim scan
anywhere it runs. That is bounded — by the structured composition on the prose side, by the
correctness gates on the content side — rather than eliminated.

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
