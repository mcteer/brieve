# Contract: the ten-operation catalogue

**Feature**: `specs/011-api-operations`
**Status**: Planned
**Recorded in**: `specs/008-northbound-api/contracts/operations.snapshot.json` — the file
the parity row compares both transports against, which is why this contract lists paths.

## The catalogue after this feature

| # | Operation | API | MCP tool | New |
| --- | --- | --- | --- | --- |
| 1 | Start a run | `POST /runs` | `start_run` | 008 |
| 2 | One run's state | `GET /runs/{run_id}` | `get_run` | 008 |
| 3 | Evidence read | `GET /evidence` | `read_evidence` | 008 |
| 4 | Request mapping change | `POST /claim-mappings` | `request_mapping_change` | 008 |
| 5 | **Collect a change's disposition** | `GET /claim-mappings/{accessor}` | `collect_mapping_change` | **011** |
| 6 | **List my runs** | `GET /runs` | `list_runs` | **011** |
| 7 | **A run's result** | `GET /runs/{run_id}/result` | `get_run_result` | **011** |
| 8 | **Stop a run** | `POST /runs/{run_id}/stop` | `stop_run` | **011** |
| 9 | **List agent definitions** | `GET /agent-definitions` | `list_agent_definitions` | **011** |
| 10 | **One definition (public view)** | `GET /agent-definitions/{id}` | `get_agent_definition` | **011** |

Every 011 operation lands on **both** transports in the same change, snapshot-first: grow
the snapshot, watch the parity row fail, add both surfaces, watch it pass. The row is the
loop, not the audit.

## Operation notes, where the behaviour is not obvious from the name

**5 — Collect.** Read-only by construction: it calls Vault's *status* endpoint, and
authorization is a different endpoint this platform never calls. The change-request record
gates who may ask — the caller must be the requester, in the requester's tenant; anything
else answers as not-found. Pending is a legitimate answer indefinitely.

**6 — List.** Tenant first, subject second, keyset cursor, bounded page. The response
never discloses withholding — no counts, no totals, no "page 3 of 7".

**7 — Result.** Three-way disposition (FR-007): not finished / the result / ended without
one. Never the raw checkpoint payload — checkpoint shape is resume state, and returning it
wholesale makes it a compatibility surface.

**8 — Stop.** Writes `STOPPED` + `stopped_by:<subject>` to the durable run record and
returns. The run observes it at its next step boundary — the in-flight step completes and
brackets, no further step begins, zero intents left open (C3). Only the starter may stop
(FR-010); stopping a terminal run reports the existing state (FR-011). Not instant, on
purpose.

**9/10 — Definitions.** Public view only: display fields plus `may_start`. Never
`ceiling_policies`, never paths (FR-014). Within the tenant everything appears, marked;
across tenants nothing does (FR-013a).

## What is deliberately absent

- **Threads** — deferred to the portal (C1), where the consumer is.
- **Any mutation of the four 008 operations** — out of scope by spec.
- **A count or total anywhere** — FR-004; the count is information.
