# Contract: What a finished authoring run leaves behind (052)

**Stability**: interface stable now. `core/authoring/retention.py` is sealed core, touched
additively; the durability seam is **used, not widened** — no new provider method, because
`save` already upserts by `blob_id`.

---

## 1. `scrub_proposal_payload`

```python
def scrub_proposal_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], int]: ...
```

`src/core/authoring/retention.py`, beside `CONTENT_BEARING_TOOLS` — the same knowledge, one
record over.

Returns the rewritten payload and the number of file bodies cleared.

### 1.1 Cleared

| Path in the payload | Cleared to | Why |
| --- | --- | --- |
| `authoring_proposal.files[].body` | `""` | The customer's file content |
| `authoring_proposal.rationale` | `""` | Model-authored, derived from the subject. FR-032 already treats it as content reaching the customer's repository |

### 1.1a Added

| Path | Value | Why |
| --- | --- | --- |
| `authoring_proposal.scrubbed` | `true` | Says **why** the bodies are empty. Without it, a scrubbed payload and a run that authored nothing are indistinguishable, and `proposal_from_payload` cannot refuse one without refusing the other |

**A marker, not an emptiness test.** `proposal_from_payload` does `str(f["body"])`, which
succeeds on `""` — verified, not assumed — so with emptied keys (§1.3) it returns a proposal
with no content, which is the empty-pull-request outcome the refusal exists to prevent.
Refusing on *emptiness* was rejected: nothing forbids a legitimately empty authored file, so
that rule would refuse proposals nobody scrubbed.

### 1.2 Kept, and asserted as kept

`files[].path`, `files[].is_diff`, `provenance`, `title`, `usage`, `task`,
`target_repository`, `branch`, `disclosures`, `evidence`, `state`.

**`provenance` is the load-bearing one.** It already carries a path-and-digest line per
authored file, so FR-009 preserves rather than adds. A row asserts it survives **by name**
rather than inferring it from the cleared list — an omission there is how US2 fails silently.

### 1.3 Properties

- **Pure.** No store, no clock, no run object.
- **Total.** A payload with no `authoring_proposal` returns unchanged, count `0`.
- **Idempotent.** Re-scrubbing returns the payload unchanged, count `0`.
- **Emptied, never removed.** Keys are set to `""`; a reader distinguishing absent from emptied
  would treat a scrubbed run as malformed.
- **The count is the assertion.** "Scrubbed nothing" and "scrubbed everything" are otherwise the
  same silent success — 041's SQL already records this reasoning.

---

## 2. When it runs

`src/surfaces/dispatch/entrypoint.py`, at the existing scrub site.

```
PROPOSER branch:  _publish_the_proposal(...)   → writes the TERMINAL payload
                  returns 0
                  scrub_proposal_payload → save(blob)          ← HERE
analyzer branch:  checkpoint_run(...)          → the handoff the proposer reads
                  NO payload scrub                              ← MUST NOT
```

**Gated to the proposer branch only.** The adjacent intents scrub is gated
`authoring_role(...) is not None`, which is true in the analyzer as well. That is safe for
intents — its SQL clears closed brackets only — and is a durability defect for the payload:
the analyzer's checkpoint *is* the handoff, and scrubbing it there makes every publish resume
with nothing to publish.

**Copying the existing gate one line down is how this feature ships broken.** Row A4 exists for
that specific mistake.

**Ordering**: after `_publish_the_proposal` returns 0. That function writes the terminal payload
itself; the scrub rewrites what it just wrote. A scrub before publish clears what publish is
about to read, and re-deriving from `checkpoint.payload` resurrects the analyzer snapshot — a
defect the call site's own comment records somebody hitting.

**Persistence**: `DurabilityProvider.save` with the same `blob_id`. No new provider method
(ADR-0024, Principle V — the seam is used).

### 2.1 The re-save carries every field

`save()` **overwrites the whole row**, and the store's own comment calls the default *"the
trap"*. Two columns are guarded and the rest are not:

| Column | Bare re-save | Guard |
| --- | --- | --- |
| `payload` | replaced — intended | none |
| `run_state`, `stop_reason` | safe | `COALESCE` — terminal-once |
| `resume_count` | safe | `GREATEST` — monotonic |
| **`correlation_id`** | **blanked** | **none** |
| `grant_id`, `step_index`, `written_by` | blanked / reset | none |

**The scrub MUST construct its blob from the TERMINAL one, replacing `payload` and nothing
else — and MUST re-read it rather than reusing what is in scope.**

`_publish_the_proposal` returns `int`, not the blob it wrote. The only blob the caller holds is
`checkpoint`, loaded **before** publish, and threading from it is the defect the call site's own
comment records: *"restored the analyzer snapshot, wiped `pr_url`, and left Nomad 'complete'
looking like 'Ended without a pull request.'"* So: `durability.load(blob_id)` first.

Blanking `correlation_id` is a governance defect, not untidiness: it is the ID joining prompt →
hook decision → tool call → product run → audit entry, `AGENTS.md` requires it propagated
through every new code path, and Principle IX's attestation is walked along it. US2 exists to
keep a run attestable, so a literal reading of "save the scrubbed payload" would destroy what
US2 protects in the commit that protects it.

Row A17 asserts every column survives. The two SQL guards protect the two columns somebody
already lost; they are not a reason to trust the next unguarded one.

---

## 3. Refusals

| Condition | Behaviour |
| --- | --- |
| The save fails | The run stops with the reason recorded (FR-005). **Never a clean report over content still in the store** — that is the failure nothing can detect afterwards |
| The provider predates `save` | Not possible; `save` is the protocol's oldest method. 041's older-provider allowance does not transfer and is deliberately not reproduced |
| The payload has no proposal | Returns unchanged, count `0`, no save, no error (FR-006) |
| Already scrubbed | Same — detected by the `scrubbed` marker, not by empty bodies. Terminal state can be reached twice |
| `proposal_from_payload` on a scrubbed payload | **Refuses**, on the marker. A fail-closed guard beside the ordering guarantee rather than instead of it |

**Asserted against the store, not the return value.** A scrub that returned a count while
leaving the row intact is exactly the shape FR-005 is about, so the row reads the stored JSON
back.

---

## 4. What a scrubbed run must still support

- A **RunReport** compiles, validates, names every path authored, and states the outcome
  (FR-003).
- The **pull request is identifiable** from the record (FR-004).
- The report **does not claim** to carry content it no longer has.
- `provenance` still lets a reviewer hash the merged pull request and match it against what the
  run recorded proposing (FR-009).

---

## 5. The backfill

`infra/bin/backfill_proposal_payloads.py` with a `backfill-proposal-payloads` wrapper —
one-time, idempotent, operator-invoked. Beside the other operator tooling, following the
`corpus_sync.py` / `corpus-sync` pairing.

- **Scope**: terminal checkpoints only. A non-terminal one may still resume.
- **Function**: the same `scrub_proposal_payload`. A second implementation could disagree with
  the first.
- **Reports** each blob it changed. A silent backfill is indistinguishable from one that did
  nothing.
- **Not a scheduled sweeper.** FR-011's never-terminal case has zero instances today, so a job
  would be operated machinery with nothing to sweep (Principle VI).

**Six checkpoints, ~81 KB, all `completed`** at the time of writing. #219's row sweeps the whole
table rather than runs created after the change, so without the backfill the feature does not
close the issue it was written for.

---

## 5.1 Scope

The scrub reaches authoring runs only (FR-012). The call sits inside the `PROPOSER` branch, so
the scoping is structural — and row A18 asserts it anyway, because a structural property is
exactly what somebody undoes by hoisting a call one line out of a branch, and every other row
would still pass.

---

## 6. Deliberately unchanged

The intents scrub and its scoping; the durability provider protocol; the checkpoint schema; the
audit trail; and `proposal_from_payload`, which stays strict — it reads `body` and will raise on
a scrubbed payload, which is correct, because it is only called before publishing and a scrubbed
payload reaching it means the ordering broke.
