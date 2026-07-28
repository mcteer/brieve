# Quickstart: validating the widened catalogue

**Feature**: `specs/011-api-operations` | **Date**: 2026-07-28

How to prove the feature end to end against a live enclave. Commands marked **(runs
today)** are the Phase 0 probes; re-running them checks the ground has not moved.

## Prerequisites

```bash
make dev-up && make dev-status
export VAULT_ADDR=$(grep '^VAULT_ADDR=' .env | cut -d= -f2- | tr -d '"')
export VAULT_CACERT=$(grep '^VAULT_CACERT=' .env | cut -d= -f2- | tr -d '"')
export VAULT_TOKEN=$(grep '^VAULT_ROOT_TOKEN=' .env | cut -d= -f2- | tr -d '"')
```

## 1 — The gaps are real *(runs today)*

```bash
# The status endpoint collect will use exists and takes an accessor:
vault path-help sys/control-group/request

# The read policy cannot list registrations (enumeration's missing capability):
vault policy read harness-authority-read | grep -A1 registration
# -> capabilities = ["read"]        # no "list"

# Nothing durable knows who started a run:
grep -c subject_user_id src/core/durability/schema.sql
# -> 0
```

## 2 — Parity is the loop *(after snapshot grows)*

```bash
uv run --extra adapters --extra surfaces pytest tests/conformance/mcp/test_surface_parity.py -q
```

**Expect**: red after the snapshot grows and before both surfaces exist; green when the
catalogue is ten on both. If it is green with fewer than ten in the snapshot, the row is
comparing the wrong set.

## 3 — Collect, end to end *(after implementation)*

```bash
# Submit a gated change, note the accessor, approve out of band, collect:
# 1. POST /claim-mappings           -> 202 + accessor
# 2. GET  /claim-mappings/{accessor} -> pending
# 3. approve via the 007 flow
# 4. GET  /claim-mappings/{accessor} -> approved
```

**Expect**: the disposition changes with zero out-of-band notification to the requester —
and polling in step 2 any number of times advances nothing.

## 4 — List, result, stop *(after implementation)*

```bash
# List: start runs as two subjects; each lists only their own, bounded, no counts.
# Result: not-finished while running; the result after; disposition+reason for a stop.
# Stop: mid-step -> the step completes and brackets, no next step, terminal,
#       zero open intents:
uv run --extra adapters --extra surfaces pytest tests/conformance/identity -m "not host_enclave" -q
```

## 5 — The sweeper ignores a stopped run *(after implementation)*

The row that proves stop is withdrawal rather than the pause ADR-0049 removed: stop a run,
mark its dependency healthy, sweep, and assert nothing resumes. Asserted against 009's
`_is_suspended`, not rebuilt.

## 6 — Enumeration disclosure and its boundary *(after implementation)*

```bash
# Two subjects, same tenant: same definitions, different may_start.
# Any subject, other tenant: nothing.
# Every response: zero ceiling_policies, zero paths.
```

## What a passing run does NOT prove

- Anything about the portal's experience of these operations — that is its feature.
- Multi-approver quorum choreography beyond what 007 exercises.
- Pagination behaviour at scale; bounded and stateless is the claim, pleasant is not.
