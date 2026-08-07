# Data Model: Authoring becomes reachable

Most entities exist (038) and are consumed unchanged: `Trees`, `AuthoredArtifact`,
`Proposal`/`ProposalState`, `Provenance`/`ProvenanceLedger`, `AuthoringRequest`,
`InstallationToken`, `AuthoringCredentials`. This file records what is **new or widened**.

## New entities

### AcquiredSubject (`core/authoring/acquisition.py`)

The platform-produced checkout that becomes the analyzer's subject mount (FR-026).

| Field | Type | Notes |
| --- | --- | --- |
| `target_repository` | `str` | The repository the request named; already validated against `owned_repositories` |
| `path` | `Path` | Per-run checkout directory, outside the tier; becomes `NOMAD_META_subject_path` |
| `commit` | `str` | Resolved HEAD SHA at clone time — the proposal's base, recorded so "the repository moved" is detectable |
| `size_bytes` | `int` | Working-tree size, checked against the acquisition bound |

**Validation**: produced only after `AuthoringRequest.validate()`; `resolve_subject_mount`'s
`subject_is_platform_tree` refusal runs against `path`. Shallow, single-branch, default branch.

**Refusal codes** (extend `RequestRefused`, FR-028): `subject_unreachable`,
`revision_missing`, `acquisition_refused` (bound exceeded — carries the size, never content).

**Lifecycle**: created pre-dispatch → mounted read-only → deleted after the run's terminal
state. Never checkpointed (a path into the dispatcher's filesystem is meaningless to a revival
on another node; revival re-acquires at the recorded `commit`).

### PublishResult (`core/authoring/publish.py`)

What `open_proposal`'s production handler returns and the observer can re-derive.

| Field | Type | Notes |
| --- | --- | --- |
| `repository` | `str` | Where it was opened |
| `branch` | `str` | `branch_for(idempotency_key)` — deterministic, the idempotency mechanism |
| `number` | `int` | Forge PR number |
| `url` | `str` | What `PROPOSAL_OPENED`'s payload carries |
| `reused` | `bool` | An existing open PR for this head was found and reused (R10) |

**Never carried**: the token, the description text (content stays out of the trail — FR-013;
the trail gets repository/branch/number/digests).

### Proposal description (composed value, not a stored entity)

`rationale` (model-authored, scanned — FR-032) + platform-authored provenance block:
correlation ID, consulted subject paths in read order, per-file content digests, truncation
note when the read was partial (FR-031). Assembled at compose time; exists only in the proposal.

## Widened entities

### Platform tool tables (`surfaces/handlers.py`, `surfaces/toolset.py`)

- `PLATFORM_HANDLERS` gains `read_subject`/`author_file` **indirectly** (per-run registration —
  they hold run state, so they cannot live in a module-level table; the entrypoint branch calls
  `register_authoring_tools` instead) and `open_proposal`'s publish handler is constructed
  per-run with the run's token source.
- **New**: `PLATFORM_TOOL_PRODUCTS: dict[str, str]` — tool → product for platform tools
  (`open_proposal` → `github`). `dependency_products()` merges it with the pack-derived map
  (FR-029). A registered suspendable tool absent from both maps fails a unit row (FR-030).
- `PLATFORM_PROBES` gains `github` (FR-029).

### Trust fabric records (`infra/modules/trust-fabric/`)

- `model_matrix_cells` gains `write` cells (both packs × Sonnet 5) with ADR-0063 mechanical
  qualification named and dated evidence in the record's comment (FR-012a).
- No new credential records: the App key path (`harness-authority/data/authoring/vcs-app`)
  exists per ADR-0062; this feature reads it.

### Capability ledger (`tests/unit/capability_inventory.py`)

`DELIBERATELY_UNREACHABLE` loses `read_subject`, `author_file`, `open_proposal` (FR-015). The
sweep then requires all three reachable — which is the row that fails if registration regresses
(FR-018 partner, US4).

### `AuthoringCredentials.token_for()` (`core/authoring/credential.py`)

`NotImplementedError` is replaced by the App JWT → installation-token exchange. Shape
unchanged; two callers (acquisition pre-dispatch, proposer in-task — R5). `available()`
untouched: the analyzer's structural absence of identity remains the control.

## State transitions

- **Run flow** (unchanged machinery, first real traversal): analyzer runs → checkpoint →
  `RUN_CONTINUE=1` proposer → publish → terminal. No resume attempt consumed (FR-009).
- **Outage**: publish suspends on product `github` → sweeper matches product recovery →
  revival → observer resolves existing-PR question → reuse or create (SC-012, R10).
- **ProposalState**: existing enum; `PROPOSAL_OPENED` now emitted by a production path.
