# Data Model: A finished authoring run leaves no proposal behind

**Feature**: 052 | **Date**: 2026-08-27 | **Plan**: [plan.md](plan.md)

No new entity, no schema change, no new provider method. This feature changes what one existing
record holds after a run finishes.

---

## 1. The stored proposal — before and after

`PROPOSAL_PAYLOAD_KEY = "authoring_proposal"` inside `checkpoints.payload`, written by
`proposal_payload` ([authoring.py:162](../../src/surfaces/dispatch/authoring.py#L162)).

| Field | After the scrub | Why |
| --- | --- | --- |
| `files[].path` | **kept** | What was touched. The smallest thing that keeps the record readable |
| `files[].is_diff` | **kept** | Whether the path was created or edited — a fact about the change, not its content |
| `files[].body` | **cleared** | The customer's file content. The whole subject of FR-033 |
| `rationale` | **cleared** | Model-authored and derived from the subject. FR-032 already classes it as content reaching the customer's repository, so keeping it would contradict a decision already taken |
| `provenance` | **kept** | **Already carries the path-and-digest manifest** — see §2. This is what makes US2 hold |
| `title` | kept | Prose *about* the change, not an extract *from* it |
| `usage` | kept | How to adopt the change. Written for the reviewer, not lifted from the repository |
| `task` | kept | What the person asked for. Their words, already in the trail |
| `target_repository`, `branch` | kept | Where the proposal went. Needed to find the pull request |
| `disclosures`, `evidence`, `state` | kept | Platform-authored statements about the run |

**`is_diff` stays with a cleared body, deliberately.** A diff's body is a diff of customer
content and goes; whether the path was created or edited is a fact about what the run *did*.

---

## 2. The manifest already exists

FR-009 is a **preservation** requirement, not an addition. `provenance` is written with one
line per authored file, path and content digest, before this feature exists:

```
Run: `propose-1df2fcf1bfa9663b`
Analysed at commit `8e97b19acc596a4a6ced42af3a91449b15180e86`
Consulted 1 subject path(s): `README.md`
`src/config/vaultConfig.js` — `59eab8f7cb9bac1fe05b328bd6c7985f9755a399b2fe5ba7225292e1d7d56f12`
`src/integrations/vault/vaultClient.js` — `0f3aef65222672363f83f0c39ec9347d7e170dd045d149a2ec8ffd91abd2e2a5`
```

So after the scrub a reviewer can take the merged pull request, hash each file, and compare
against what the run recorded proposing — with the platform holding none of the content.

**This is why US1 and US2 do not trade against each other.** Had the manifest needed inventing,
"keep enough to attest" and "keep nothing of the customer's" would have been in tension. They
are not: the record already says what it needs to.

**The scrub must not touch `provenance`**, and a row asserts that specifically rather than
relying on it being absent from the cleared list.

---

## 3. `scrub_proposal_payload` — new, pure

`src/core/authoring/retention.py`, beside `CONTENT_BEARING_TOOLS`.

```
scrub_proposal_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], int]
```

Returns the rewritten payload and the number of file bodies cleared.

| Property | Rule |
| --- | --- |
| **Pure** | Takes a payload, returns a payload. No store, no clock, no run. Testable without a database |
| **Total** | A payload with no `authoring_proposal` returns unchanged, count 0 — a run that authored nothing and one that published must not take different cleanup paths (FR-006) |
| **Idempotent** | Scrubbing an already-scrubbed payload returns it unchanged, count 0. Terminal state can be reached twice |
| **Non-destructive of structure** | Keys are cleared to `""`, never removed. A reader distinguishing "absent" from "emptied" would otherwise treat a scrubbed run as a malformed one |
| **Count is the assertion** | "Scrubbed nothing" and "scrubbed everything" are otherwise the same silent success — the reasoning 041's SQL already records |

**Where the knowledge lives.** *What counts as content* is authoring knowledge and belongs
beside `CONTENT_BEARING_TOOLS`. *How a payload is stored* is the durability provider's, and is
already provided. Selecting fields in SQL would put the first inside the second.

---

## 4. When it runs

`src/surfaces/dispatch/entrypoint.py`, at the existing scrub site
([entrypoint.py:1500](../../src/surfaces/dispatch/entrypoint.py#L1500)).

```
if authoring_role(...) == PROPOSER:
    published = _publish_the_proposal(...)     # writes the TERMINAL payload
    if published != 0: return published
else:
    checkpoint_run(...)                        # analyzer: the handoff the proposer will read

if authoring_role(...) is not None:
    scrub_authoring_requests(...)              # intents — BOTH branches, safe
                                               # payload  — PROPOSER branch only  ← new
```

**The gating is the part that can break the platform.** `authoring_role(...) is not None` is
true in the analyzer too. That is safe for intents, whose SQL clears closed brackets only, and
would be a defect for the payload: the analyzer's checkpoint *is* the handoff, and scrubbing it
there makes every publish resume with nothing to publish. Copying the existing gate one line
down is the way this feature ships broken (US3).

**Ordering**: after `_publish_the_proposal` returns 0, because that function writes the terminal
payload itself. The scrub rewrites what it just wrote, through `save` — which upserts by
`blob_id`, so no new provider capability is needed.

---

## 5. What does not change

| | |
| --- | --- |
| `intents.arguments` scrub | Untouched. 041's narrow scoping and its older-provider handling stand |
| The durability provider protocol | No new method. `save` already upserts by `blob_id` |
| The checkpoint schema | No migration |
| `proposal_from_payload` | Unchanged, and it must stay strict: it reads `body` and will raise on a scrubbed payload. That is correct — it is only called before publishing, so a scrubbed payload reaching it means the ordering broke, and it should fail loudly rather than reconstruct an empty proposal |
| The audit trail | Not a subject here. FR-013 already refused the trail a copy nobody can delete |

---

## 6. The backfill

`scripts/backfill-proposal-payloads.py` — one-time, idempotent, operator-invoked.

Six checkpoints hold a proposal today, ~81 KB, **all `completed`**. A forward-only scrub leaves
every one of them, and #219's acceptance row sweeps the whole table rather than runs created
after the change — so without this the feature does not close the issue it was written for.

| Property | Rule |
| --- | --- |
| Scope | Terminal checkpoints only. A non-terminal one may still be resumed |
| Function | The same `scrub_proposal_payload`. A second implementation could disagree with the first |
| Idempotent | Safe to re-run; reports how many it cleared |
| Reports | Names each blob it changed. A silent backfill is indistinguishable from one that did nothing |

**A script rather than a sweeper.** FR-011's never-terminal case has zero instances today, so a
scheduled job would be operated machinery with nothing to sweep (Principle VI). The six rows
are a fixed, finite set.
