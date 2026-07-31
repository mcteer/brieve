<!-- SPDX-License-Identifier: Apache-2.0 -->
# Quickstart: validating 018 registry isolation

## Prerequisites

- A local enclave: `make dev-up`
- `.env` with the enclave's coordinates

## Run it

```bash
make conformance          # the rows run on the host_enclave line
```

Or alone:

```bash
uv run pytest tests/conformance/authority -m host_enclave -q
```

Expected: every bounding path refuses a write, and every refusal is attributable because the
same authority can read the path.

## Prove it can fail — by hand, once, never in a lane

**This grants a run write access to its own ceiling on a real control plane.** Do it on your
own enclave, record the output, and revoke it. Do not automate it: a fixture killed between
grant and revoke leaves the platform permissive with nobody watching.

1. Add a write capability to the run's read policy on one bounding path.
2. Run the rows. Expected: red, reporting **that the write was permitted** — not "assertion
   failed", and the row should have removed what it wrote (FR-004b).
3. Revoke the capability.
4. **Verify the revocation took**, and record that you did. Not "I ran the revoke command" —
   check that the write is refused again.

Paste the output into [contracts/conformance.md](contracts/conformance.md).

## Prove the attribution guard works

The reason this feature is not one line. Point a row at a path with a typo:

```
harness-authority/data/harness-ceilingz/planner-agent
```

Expected: the row **fails**, reporting that the refusal could not be attributed. If it
passes, the guard is absent and the gate would accept a typo as proof of isolation — which
was the state of the world before this feature.

## Confirm nothing else stopped running

```bash
uv run pytest tests/conformance --collect-only -q | tail -1
```

Compare the per-directory counts against `main`. Comparing totals proves nothing — this
feature adds rows.
