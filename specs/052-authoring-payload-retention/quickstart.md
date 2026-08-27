# Quickstart: A finished authoring run leaves no proposal behind (052)

**Feature**: 052 | **Plan**: [plan.md](plan.md) | **Contracts**: [payload-retention.md](contracts/payload-retention.md)

How to prove this works end to end. Implementation belongs in `tasks.md`; this is the
validation guide.

## Prerequisites

```bash
uv sync --all-extras
```

Scenarios 1–3 are hermetic. Scenarios 4–6 need `make dev-up`.

> **`uv sync --all-extras`, not `--extra <one>`.** A single-extra sync *replaces* the installed
> set rather than adding to it, and breaks ~70 modules at import. Learned on 051.

---

## Scenario 1 — The right fields go, and the right ones stay (A1–A3, A6)

```bash
uv run pytest tests/unit/test_proposal_payload_scrub.py -q
```

**Expect**: bodies and `rationale` emptied to `""`; `path`, `is_diff`, `title`, `usage`,
`task`, `target_repository`, `branch`, `disclosures`, `evidence`, `state` untouched; and
`provenance` present with its path-and-digest lines intact.

**A3 is the row to watch.** US1 and US2 only coexist because the manifest already lives in
`provenance`. A change that cleared the whole proposal would satisfy retention, destroy
attestation, and look tidier while doing it.

Read what survives:

```bash
uv run python -c "
from core.authoring.retention import scrub_proposal_payload
payload = {'authoring_proposal': {
    'files': [{'path': 'main.tf', 'body': 'resource \"aws_vpc\" \"main\" {}', 'is_diff': False}],
    'rationale': 'derived from the subject repository',
    'title': 'Add a VPC',
    'provenance': ['\`main.tf\` — \`abc123\`'],
}}
scrubbed, count = scrub_proposal_payload(payload)
p = scrubbed['authoring_proposal']
print('cleared     :', count)
print('body        :', repr(p['files'][0]['body']))
print('rationale   :', repr(p['rationale']))
print('path kept   :', p['files'][0]['path'])
print('provenance  :', p['provenance'])
"
```

---

## Scenario 2 — Total and idempotent (A7, A8)

```bash
uv run pytest tests/unit/test_proposal_payload_scrub.py -k "empty or twice" -q
```

**Expect**: a payload with no `authoring_proposal` returns unchanged with count 0 and triggers
no save; scrubbing twice returns unchanged with count 0. A successful run and an empty one must
not take different cleanup paths, and terminal state can be reached twice.

---

## Scenario 3 — A scrubbed payload cannot be published (A10)

```bash
uv run pytest tests/conformance/authoring/ -k "scrubbed_payload" -q
```

**Expect**: `proposal_from_payload` **raises**. It is only called before publishing, so a
scrubbed payload reaching it means the ordering broke — and it must fail loudly rather than
reconstruct a proposal with empty bodies and open an empty pull request.

---

## Scenario 4 — The analyzer does not scrub (A4) 🔴 the one that breaks the platform

```bash
make dev-up
uv run pytest tests/conformance/durability/ -k "analyzer_handoff" -q
```

**Expect**: at the analyzer handoff the payload still carries every body.

The adjacent intents scrub is gated `authoring_role(...) is not None`, which is **true in the
analyzer too**. That is safe for intents and a durability defect for the payload: the
analyzer's checkpoint *is* the handoff the proposer reads. Copying that gate one line down
makes every publish resume with nothing to publish.

---

## Scenario 5 — Stored text, not just the object (E1)

```bash
bash infra/bin/enclave-conformance
```

**Expect** the round-trip row green: a scrubbed payload saved to the real store, read back, and
the bodies absent from the **stored JSON text**.

> 041's Postgres leg exists because in-memory clears a field for free. That argument does not
> transfer — this feature writes no SQL, since `save` already upserts by `blob_id`. What can
> still go wrong is saving the pre-scrub object, and only the stored text shows that.

---

## Scenario 6 — The backfill, and #219 goes green (E2, SC-006)

Count first, so the backfill has something to have done:

```bash
set -a; . ./.env; set +a
uv run python -c "
import sys; sys.path.insert(0,'tests')
from tests.conformance.durability import dispatch_harness as h
c = h.connection()
rows = h.query(c, \"SELECT blob_id, run_state FROM checkpoints WHERE payload::text LIKE '%authoring_proposal%'\")
print(f'holding a proposal: {len(rows)}')
for r in rows: print(' ', r[0], r[1])
c.close()"
```

**Expect before**: 6, every one `completed`. Then:

```bash
uv run python scripts/backfill-proposal-payloads.py
make conformance
```

**Expect**: the backfill names each blob it changed; re-running it clears 0; and
`test_row_checkpoints_still_hold_no_credential_material` — the row from
[#219](https://github.com/mcteer/brieve/issues/219) — **passes**, which is this feature's
acceptance signal.

> A forward-only scrub leaves all six. That row sweeps the whole table, not runs created after
> the change, so without the backfill the feature does not close the issue it was written for.

---

## Scenario 7 — The run is still attestable (A12–A14, US2)

```bash
uv run pytest tests/conformance/reports/ -k "scrubbed" -q
```

**Expect**: a RunReport compiled from a scrubbed run validates, names every authored path,
states the outcome, keeps the pull request identifiable, and **does not claim** to carry
content the run no longer holds.

Then the manual check that matters — take a merged pull request from a scrubbed run, hash each
file, and compare against the run's `provenance` lines. They match, and the platform holds none
of the content. That is the whole argument for why clearing it is safe.

---

## Full gate before merge

```bash
make check
make conformance     # includes the durability lane and #219's row
make test-full
```

**Security-maintainer review is required**: `core/authoring/retention.py` is sealed core, and
this change deletes content a run record currently contains.
