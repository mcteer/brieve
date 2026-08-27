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

---

## 3. Refusals

| Condition | Behaviour |
| --- | --- |
| The save fails | The run stops with the reason recorded (FR-005). **Never a clean report over content still in the store** — that is the failure nothing can detect afterwards |
| The provider predates `save` | Not possible; `save` is the protocol's oldest method. 041's older-provider allowance does not transfer and is deliberately not reproduced |
| The payload has no proposal | Returns unchanged, count `0`, no save, no error (FR-006) |
| Already scrubbed | Same. Terminal state can be reached twice |

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

`scripts/backfill-proposal-payloads.py` — one-time, idempotent, operator-invoked.

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

## 6. Deliberately unchanged

The intents scrub and its scoping; the durability provider protocol; the checkpoint schema; the
audit trail; and `proposal_from_payload`, which stays strict — it reads `body` and will raise on
a scrubbed payload, which is correct, because it is only called before publishing and a scrubbed
payload reaching it means the ordering broke.
