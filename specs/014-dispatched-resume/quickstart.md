# Quickstart: validating dispatched resume

**Feature**: `specs/014-dispatched-resume` | **Date**: 2026-07-29

## Prerequisites

```bash
make dev-up && make dev-status
```

## 1 — The gap is real *(runs today, before implementation)*

```bash
# resume_run has no caller in src/ — the finding this feature exists to close
grep -rn "resume_run(" src/ --include="*.py" | grep -v "def resume_run" | wc -l   # -> 0

# The entrypoint writes the CREDENTIAL id into the grant_id column (research F1)
grep -n 'grant_id=getattr(run.authority, "credential_id"' src/surfaces/dispatch/entrypoint.py

# Nothing persists a grant anywhere
grep -rn "save_grant\|grants (" src/core/durability/ | wc -l                      # -> 0
```

## 2 — A disrupted run completes exactly once *(after implementation)*

```bash
# The whole feature in one lane — 005's properties, through a dispatch:
uv run --extra adapters --extra surfaces --extra portal pytest \
  tests/conformance/durability -m host_enclave -k "dispatch" -q
```

**Expect**: kill mid-run → sweep → new allocation → completion, with already-completed
steps at exactly one execution. See
[contracts/conformance-resume.md](contracts/conformance-resume.md) for the full row list.

## 3 — Re-observation, live, both directions

**Expect**: an interrupted `vault_write` whose effect landed is skipped; one whose effect
did not land proceeds — against real Vault, with the shipped observer, per clarify Q3. The
row arranges each external state at the probe path before resuming.

## 4 — The suspension cycle and the cap

**Expect**: an open `terraform_apply` intent suspends the resumed run awaiting `terraform`
(the product, not the tool); `record_probe("terraform", reachable=True)` revives it with no
human action; flapping revives it exactly `RESUME_ATTEMPT_CAP` times and then stops it
terminally with `resume_attempts_exhausted`.

## 5 — Consent, expired

**Expect**: a resume under a lapsed grant stops with the reason recorded and zero
subsequent steps; renewing consent revives nothing. This is checkable **only because the
grants table exists** — before this feature, the dispatched path had nothing to check
expiry against (research F1).

## 6 — The record is re-scoped (FR-020)

```bash
# 005's scope note must now point here instead of scoping to the function:
grep -n "asserted through a dispatch" specs/005-durable-execution/contracts/conformance-durability.md
# And ROADMAP gap 0a is closed:
grep -n "0a\." ROADMAP.md   # -> the entry states it is closed, or is gone
```

## What a passing run does NOT prove

- **Recovery under a real product outage** — the harness flaps a fixture product on purpose
  (stopping Vault would take the trust fabric down with the product under test).
- **That five is the right cap** — exhaustion being terminal and recorded is the property;
  the number is a tunable starting point.
- **Cross-build resume compatibility** — these rows resume runs their own harness started.
