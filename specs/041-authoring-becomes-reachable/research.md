# Research: Authoring becomes reachable

Every decision below was checked against merged `main` (`f4f9f5c` at spec time) rather than
inferred. Where a decision was made during clarification, this file records the mechanics under
it, not the decision again.

## R1 — How the entrypoint learns it is an authoring run

**Decision**: Branch on `HARNESS_AUTHORING_ROLE`, which the jobspec already sets (`analyzer` /
`proposer`) and the entrypoint never reads. The analyzer branch builds `Trees` from the mounted
`/subject` and the allocation's workspace, calls `register_authoring_tools(registry, trees=...,
artifact=...)` after `build_registry()`, and runs the standard dispatched model loop (040's
chooser) with the trio in the vocabulary. The proposer branch takes the existing `RUN_CONTINUE`
path — already implemented and checked before the resume branch — and calls
`register_proposal_tool` with the new publish handler.

**Rationale**: Both seams exist and were built for exactly this. The jobspec's env contract
(`RUN_REQUESTED_TOOLS`, `RUN_CONTINUE=1` on the proposer) was authored by 038 with the
entrypoint in mind; the entrypoint just never grew the branch. Registration stays per-run
because the handlers hold run-scoped state (workspace, artifact) — module-level registration was
already rejected in `tool.py`'s own docstring.

**Alternatives considered**: A separate authoring entrypoint script (rejected: two entrypoints
is two places for the D1 discriminator and the lease logic to drift); inferring the role from
which tools the ceiling grants (rejected: an inference where the jobspec already declares —
the same class of mistake D1's comment warns about for resumes).

## R2 — The transport determination (records FR-023's ADR content)

**Decision**: Native CLIs — `git` for clone and push, `gh pr create` for the proposal. Recorded
as a Principle II registry-review determination in a new ADR (0066), including the reversal:
MCP was selected first and rejected on measurement.

**Rationale**: The external surface is one clone, one push, one PR-create. The official GitHub
MCP server is a process with its own supply chain and auth model, inside the hardened tier that
exists to process untrusted repository content, exposing dozens of tools where the task's scope
is one. `gh` authenticates from `GH_TOKEN` (environment only), satisfying FR-023a without
credential plumbing. Core git alone cannot open a PR — `git request-pull` drafts a maintainer
email; a forge PR is a forge concept.

**Alternatives considered**: MCP GitHub server (rejected above — and it would have owed a
Principle VI trigger ADR as an operated component); direct REST call to
`POST /repos/{owner}/{repo}/pulls` (workable, but hand-rolled auth/retry/pagination glue around
an API `gh` already wraps — Principle I says adopt); PyGithub or similar library (a supply-chain
dependency for one endpoint).

## R3 — The pre-dispatch clone: where it runs and what governs it

**Decision**: A new `core/authoring/acquisition.py`, called by the dispatching context (the same
context that today validates `resolve_subject_mount`) **before** the Nomad dispatch. It clones
`target_repository` at its default branch into a per-run directory outside the tier, records
the resolved commit SHA, and that path becomes `NOMAD_META_subject_path`. The existing
`subject_is_platform_tree` refusal runs against the produced path — the check survives, the
input to it changes from operator-supplied to platform-produced.

**Rationale**: FR-027 forbids the clone inside the tier (the analyzer has no egress and no
credential, and must keep having neither). The dispatcher already reads governed records and
performs pre-dispatch validation; acquisition is one more refusal that happens before anything
is produced (FR-028's "refused before producing" posture, which `request.py` already states).

**Alternatives considered**: Clone inside the analyzer task (rejected: requires egress and a
credential exactly where the design forbids both); a Nomad prestart task that clones (rejected:
the credential would enter the allocation's env or meta, which the checkpoint/meta plumbing can
see — and `AuthoringCredentials` exists specifically so nothing can pass a token in); artifact
stanza with git (rejected: Nomad's git artifact support would put the token in the jobspec).

**Interaction with the audit trail**: acquisition emits its refusals through the existing
`RequestRefused` path with new reason codes (`subject_unreachable`, `revision_missing`,
`acquisition_refused`) so an operator can tell a dead repository from a bad request.

## R4 — The acquisition bound

**Decision**: A fixed clone budget: `--depth 1 --single-branch` always (history is not the
subject; the working tree is), plus a size refusal after clone if the checkout exceeds a stated
constant (default 512 MiB), disclosed in the refusal. The read budget (4 MiB) continues to
govern what the model *sees*; the acquisition bound governs what the platform will *hold*.

**Rationale**: The spec's edge case ("the clone succeeds but the repository is enormous")
requires either a bound or an explicit statement of none. A shallow single-branch clone is the
smallest artifact that is still genuinely the repository, and `READ_BUDGET_BYTES` already
establishes the pattern of a fixed threshold carried with its reasoning.

**Alternatives considered**: No bound (rejected: an unbounded platform-side fetch of
customer-named content is a resource-exhaustion vector with a name on it); partial/sparse clone
(rejected for v1: sparse checkout needs path selection nothing yet supplies — noted as the
natural extension when an intake surface exists).

## R5 — The clone credential

**Decision**: The same ADR-0062 App installation token, minted in the **dispatching context**
under that context's identity, scoped to the installation that owns `target_repository`, used
for the clone, and discarded. `token_for()` gains its real implementation (App JWT →
installation token exchange), used by both acquisition (pre-dispatch) and the proposer (in-task).

**Rationale**: One credential path, two callers, both already inside ADR-0062's wording — "read
under the reading workload's own attested identity, delivered per task, never persisted". The
`owned_repositories` check already bounds which repositories a request may name; the clone
inherits that bound because it happens after `validate()`.

**Alternatives considered**: A separate read-only deploy key per repository (rejected: a second
credential class, a second seeding path, and ADR-0062 already covers this); cloning
anonymously for public repositories only (rejected: makes the feature's central path work only
on public content, which is not the product).

## R6 — Qualifying the permanent `write` cell

**Decision**: Run the mechanical qualification that already exists — `make eval-authoring`
drives `tests/conformance/authoring -k qualification` over `evals/authoring/corpus.toml` —
against **Sonnet 5** live output for the corpus's golden tasks, record the dated evidence in
the matrix record's evidence comment (031's precedent), and add the `write` cell for both packs
to `model_matrix_cells` in the trust fabric, bound as an operator record. `promote_model_version`
accepts the cell with the mechanical scorer named per ADR-0063 (no judge — the cell cannot be
a judge, which ADR-0063 already states).

**Rationale**: FR-012a requires the qualification to be a governed act with dated evidence, and
every piece of machinery for it shipped with 038 unexercised. Sonnet 5 per the estate's standing
decision (032), not swapped mid-feature (FR-012b).

**Alternatives considered**: Seed-and-restore a demo cell (031's shape — rejected by
clarification Q2: authoring should be available, not demonstrated); qualify Opus as well
(deferred: evidence does not expire, but nothing requires a second cell now and the live lane
runs Sonnet).

## R7 — GitHub as a named product; platform tools get product mappings

**Decision**: Add a `github` probe to `PLATFORM_PROBES` (an authenticated
`gh api /rate_limit`-class reachability check from where the checker runs) and give platform
tools an explicit tool→product mapping that `dependency_products()` merges with the
pack-derived map. `open_proposal` maps to `github`. FR-030's general guard lands beside it: a
registered suspendable tool with no product mapping fails a unit row, so the next platform tool
cannot reintroduce the wait-forever suspension.

**Rationale**: The sweeper matches suspensions by product; today the trio would suspend on a
tool name no product recovery ever matches (`toolset.py` states the consequence). The probe is
keyed by product, which is what the checker probes.

**Alternatives considered**: Making publishing failure terminal (clarification Q4 option B —
rejected by the user's A); teaching the sweeper to match tool names (rejected: the sweeper's
product-keying is deliberate and shared with health checking).

## R8 — Where `git` and `gh` come from in the task image

**Decision**: The task image (`ghcr.io/astral-sh/uv:python3.12-bookworm-slim`) is **not
assumed** to carry either CLI. The proposer task installs nothing at runtime; instead the
enclave lane verifies presence-and-version at task start and **fails with a named reason**
(`tooling_missing`) if absent, and the jobspec documents the image requirement. If the base
image lacks them, the repair is a derived image built in `infra/` with pinned versions — an
implementation-time decision the tasks file carries, not silently absorbed.

**Rationale**: `bookworm-slim` variants routinely lack `git`, and `gh` is never present in
Python base images. A runtime `apt-get install` would be an unpinned network fetch inside the
hardened tier — exactly what the static-allowlist posture refuses. Verify-and-fail keeps the
gate honest while leaving the image decision where it can be tested.

**Alternatives considered**: Runtime install (rejected above); vendoring static binaries into
the repo (rejected: binaries in git, and a second copy of what a registry already distributes).

## R9 — Delivering the token to the CLIs without persistence

**Decision**: Environment only, per invocation: `GH_TOKEN` for `gh`; for `git` push,
`git -c credential.helper= -c credential.helper='!gh auth git-credential'` so git asks `gh`,
which reads `GH_TOKEN` from the environment. No token in remote URLs, no `gh auth login`, no
credential store, nothing written under `$HOME`. The subprocess environment is constructed per
call and not inherited wholesale from the task env.

**Rationale**: FR-023a. A token in a remote URL leaks into `.git/config` and process listings;
`gh auth login` writes `hosts.yml` to disk. The empty first helper clears any system-configured
helper so the only credential source is the one supplied.

**Alternatives considered**: `GIT_ASKPASS` pointing at a script that echoes the token
(workable, but the script is a file whose contents gate a credential — the `gh` helper does the
same job with no file); `http.extraheader` with a basic-auth blob (leaks via `ps` when passed
as `-c` on the command line on some platforms; the helper form passes no secret as an argument).

## R10 — Idempotent publishing against a real forge

**Decision**: `branch_for(idempotency_key)` stays the branch name. The publish handler pushes
with `--force-with-lease` to the deterministic branch and then checks for an existing open PR
for that head (`gh pr list --head <branch> --json number`) before creating one — reuse if
present, create if absent. The non-repeatable observer's `CANNOT_DETERMINE` resolution performs
the same head-branch query, which turns an interrupted publish into an observation rather than
a second proposal (SC-010, SC-012).

**Rationale**: The deterministic branch is the idempotency mechanism 038 designed;
`--force-with-lease` makes a re-publish converge on the latest contained content rather than
failing on a stale ref. The observer needs a query that distinguishes "PR exists" from "PR
absent", and the head-branch listing is exactly that.

**Alternatives considered**: Failing when the branch exists (rejected: makes every revival a
manual cleanup); `--force` (rejected: would silently clobber a human's edits to the branch —
force-with-lease refuses instead, and that refusal is the right behaviour, surfaced).

## R11 — What drives the analyzer's model loop

**Decision**: Nothing new. The analyzer branch reuses the dispatched choice path 020/040 built —
`_chooser_for` resolves the definition's bound cell (now a `write` cell via
`resolve_write_cell`), 040's structured recordings let the model supply `path`/`content`
arguments, and the trio are ordinary registered tools in the loop's vocabulary.

**Rationale**: 040 exists precisely so a model can say *what* to author. `author_file` without
model-supplied arguments would be the `_PROBE_ARGUMENTS` defect again, one feature later.

**Alternatives considered**: A bespoke authoring loop in `core/authoring` (rejected: a second
loop is a second place governance ordering must be proven; the whole point of the registry
design is that new tools join the existing loop).

## R12 — The proposal description passes containment

**Decision**: The rationale joins `scannable_text()`'s output — `compose()` already returns
scannable text per proposed file, and the description becomes one more scanned unit
(`("<description>", rationale + provenance block)`) before publish. A finding refuses the
publish with the existing `ContainmentRefused` path.

**Rationale**: FR-032 — the description is model-authored content reaching a customer's
repository; exempting prose would leave the one unscanned field. The provenance block
(correlation ID, consulted paths, digests, truncation note) is platform-authored and appended
after the scan of the model half, so a finding always names model content.

**Alternatives considered**: Scanning only the files (rejected by FR-032); a separate
description scanner (rejected: `scan_for_analysed_content` and `scan_for_secrets` are the
containment vocabulary; a parallel scanner would drift).

## Resolved unknowns from Technical Context

None remain. The one deferred-to-implementation item is R8's image question (verify-and-fail
posture defined; whether a derived image is needed is discovered by running the lane, and the
tasks file will carry it).
