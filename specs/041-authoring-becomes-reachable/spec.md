# Feature Specification: Authoring becomes reachable

**Feature Branch**: `spec/041-authoring-becomes-reachable`

**Created**: 2026-08-07

**Status**: Draft

**Input**: Measured against merged main (`f4f9f5c`) — 038 built the authoring tier and registered none of it. The gap is five layers deep, and only the first was known.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R5, R11 (total interception)** — the trio enters through the same governed pipeline every other tool does, and **registration is the opt-in switch** rather than a flag somebody sets. **R2, R3 (authority per task)** — the ceiling decides whether a definition may call these at all, and the tier's two tasks hold deliberately different scopes. **R7 (fail-closed)** — a tool that is not registered, not in the ceiling, or not permitted by task scope refuses, and refuses with a reason that names the right layer. **R4, R13 (evidence)** — what was consulted, what was authored, and what was proposed are recoverable from records rather than from the workspace. R16 (sealed core — the registry and the dispatch entrypoint are sealed-core seams, touched additively) |
| **ADRs touched** | **ADR-0038** (the hardened untrusted-content tier — built by 038, and this is the feature that lets anything reach it), **ADR-0064** (the platform-tool target that made the trio platform tools rather than pack tools), **ADR-0062** (the publishing credential — Principle IV's third named exception, which nothing has yet read), **ADR-0047** (a passing stub is worse than a missing one — 038's rows are this feature's motivating case, not its precedent), ADR-0025 (registry isolation — the trio is the first write surface to test it), ADR-0022/ADR-0039 (the `write` cell, whose resolver 038 landed and nothing calls), ADR-0026/ADR-0049 (the checkpoint-and-continue handoff, distinct from a resume), ADR-0065 (039's kept analysis: three layers, registration as the opt-in switch, the ceiling deciding, and one row where dispatched work actually runs) |
| **Evidence class** | **attestation-relevant.** The trail gains the tier's first genuine records — a run that consulted a private subject, authored files, and opened a proposal — and the authored *content* deliberately stays out of it, because an append-only store holding a copy of a customer's private repository is one nobody can delete. What changes is that these records begin to exist at all |

## Clarifications

### Session 2026-08-07

- Q: Does this feature include actually opening the pull request, or does it stop at reading and
  authoring? → A: **It includes it, against real GitHub.** The full loop ships — nothing about
  the tier's only externally visible output is faked, so there is no gate that passes while the
  feature is broken. A GitHub App installation on a maintainer-owned repository becomes an
  operator prerequisite for the enclave row.
- Q: How does the analysed subject tree come to exist, and what ties it to the repository the
  proposal is opened against? → A: **The platform clones `target_repository` before dispatch and
  mounts that checkout read-only as the subject.** The analysed tree and the published
  destination are the same thing by construction, so the mismatch cannot be introduced rather
  than being checked for. The clone happens in the dispatching context, which already reads
  governed records — **not** in the hardened tier, so the analyser still holds no credential and
  no egress.
- Q: Does the enclave row need a qualified `write` cell, and how is one obtained? → A: **Qualify a
  permanent cell through the mechanical scorer and bind it.** ADR-0063 amended ADR-0052 to permit
  exactly this and has never been exercised; `resolve_write_cell` landed with 038 and has never
  been called. Authoring becomes genuinely available in the estate rather than demonstrated once
  and withdrawn. The cell is **Sonnet 5**, per the estate's standing decision, and is not swapped
  mid-feature.
- Q: What does the proposal's description carry? → A: **The model's rationale plus
  platform-authored provenance** — correlation ID, what was consulted, content digests, and the
  truncation note when the read was partial. `compose()` already takes a `rationale` parameter
  that defaults to empty and has no caller, so this was undecided rather than decided one way.
  The reviewer needs the same disclosure the artefact already refuses to omit: 038 raises rather
  than compose a truncated artefact with no note, and a proposal that reads complete while
  resting on part of a codebase is that same defect one layer out, where the person is.
- Q: What happens when the version-control host is unreachable at publish time? → A: **GitHub
  becomes a named product with a probe, and the platform tools carry a product mapping**, so
  suspension and revival work as they do for every other product outage. This closes a hazard
  found during clarification: `dependency_products()` builds its tool→product map only from pack
  manifests, and the trio are platform tools (ADR-0064), so they carry no product today — and
  `toolset.py` states the consequence plainly, that a suspension naming a tool rather than a
  product is never matched by that product recovering. A run suspended on `open_proposal` would
  have waited forever. The non-repeatable observer already settles whether an interrupted publish
  landed.
- Q: What transport does the version-control integration use? → A: **Native CLI — `git` for clone
  and push, `gh pr create` for the proposal.** MCP was chosen first and then rejected on
  measurement. Principle II's MCP preference is *a determination made at registry review*, not an
  automatic rule, and the same clause says authoring an MCP server is never required merely for
  protocol uniformity. **The cost was lopsided**: a server process, its supply chain and its own
  auth model, running inside the hardened tier that exists to process untrusted repository
  content — and exposing dozens of tools where the publishing task's entire scope is
  `open_proposal`. **`gh` is the adopted vendor tool Principle I asks for**, authenticating from
  `GH_TOKEN` so the installation token needs no credential plumbing. Core `git` alone is
  insufficient and the reason is narrow: `git request-pull` produces a summary for emailing a
  maintainer, not a pull request on a forge.

## The gap, measured

Five layers, and 038's conformance rows are green through all five. Each was verified against
merged `main` rather than inferred:

| Layer | What exists | What is missing | How it was measured |
| --- | --- | --- | --- |
| **Registration** | `register_authoring_tools` and `register_proposal_tool` in `src/core/authoring/tool.py`, both complete | **Zero callers** — in `src/` or in `tests/`. `PLATFORM_HANDLERS` holds four Vault/Terraform tools and none of the trio | `grep` across the tree returns nothing outside the defining module |
| **Vocabulary** | `known_tools()` derives what a ceiling may name from what actually registered | A ceiling naming `author_file` refuses **`unknown_ceiling_entry`** today | `build_registry(packs=['vault','terraform'])` yields `apply, echo, plan, terraform_apply, terraform_plan, vault_read, vault_write` — the trio is absent from the vocabulary, not merely from the handler table |
| **Entrypoint** | `src/surfaces/dispatch/entrypoint.py` builds every run's registry at one seam | No authoring branch: it never reads `HARNESS_AUTHORING_ROLE`, never constructs `Trees`, never calls either registration function. **No publishing handler exists anywhere in `src/`** — `register_proposal_tool` takes a `handler` nothing supplies | The job sets `HARNESS_AUTHORING_ROLE`; the entrypoint contains no occurrence of it |
| **Job** | `infra/jobs/authoring-tier.nomad.hcl` declares `analyzer` and `proposer` with mounts, identity, lifecycle and task scope, all carefully reasoned | Neither task declares `args`. Both are `entrypoint = ["/bin/sh", "-c"]` with **nothing to run** | `grep -c args` returns `0` for this job and `agent-run.nomad.hcl` has them at line 184 |
| **Credential** | `AuthoringCredentials` accepts no credential from a caller — there is nowhere to pass a token in, which is the property the design rests on — and `available()` correctly reports the analysing task's absence of identity | `token_for()` raises **`NotImplementedError`**: the App-key exchange is "provisioned by the estate and exercised in the enclave lane", and no enclave lane has ever run it | Reading the method body; the raise is unconditional after the JWT check |

**Why every row is green anyway, and this is the finding.** 038's conformance suite constructs
`FileAuthor(trees, artifact)` and `SubjectReader(trees)` directly, and synthesizes the ceiling
with `fake_identity_fabric(ceiling_tools=permitted)`. So the rows never traverse the registration
path and never consult the derived vocabulary — they assert that the handlers behave correctly,
which is true, and say nothing about whether anything can call them. **This is the third instance
of the defect the capability ledger was built for**, and the first one the ledger named in advance
rather than being discovered by accident.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A ceiling can grant authoring (Priority: P1)

An operator writes a ceiling that grants a definition `read_subject` and `author_file`. The
record is accepted, and the definition's runs may call those tools.

**Why this priority**: This is the first layer and everything else sits on it. Today a correct
ceiling is refused with an error naming the ceiling — sending whoever reads it to look at the
record, and at the trust fabric, and never at the vocabulary the platform derived.

**Independent Test**: Author a ceiling naming the authoring tools, load it, and confirm it
resolves rather than refusing `unknown_ceiling_entry`.

**Acceptance Scenarios**:

1. **Given** a ceiling record naming `read_subject` and `author_file`, **When** it is parsed,
   **Then** it is accepted and the tools are in the definition's effective authority.
2. **Given** a definition whose ceiling omits `author_file`, **When** a run attempts it,
   **Then** it is refused for **not being in the ceiling** — a distinct reason from the tool
   being unknown, because the two send an operator to different places.
3. **Given** the fixture toolset with no packs, **When** the vocabulary is derived,
   **Then** definitions that name no authoring tools are unaffected.

---

### User Story 2 — A dispatched run reads its subject and authors a file (Priority: P1)

A dispatched analyzer run receives a subject mount, reads from it through the governed read
path, and writes files into its workspace — each call passing the same hooks, ceiling check and
records as any other tool.

**Why this priority**: This is the capability the platform has claimed since 038 and has never
performed. It is also where the governed properties either hold in a real allocation or turn out
to have held only in a constructed test.

**Independent Test**: Dispatch an analyzer run against a fixture subject and confirm the file
exists in the workspace, the read is recorded, and the injection lens saw the content.

**Acceptance Scenarios**:

1. **Given** a dispatched run whose ceiling grants the analyzer pair, **When** it reads a subject
   path and authors a file, **Then** both acts complete and both are recorded.
2. **Given** the same run, **When** it attempts to write outside its workspace,
   **Then** the write is refused and the refusal is recorded.
3. **Given** a subject exceeding the read budget, **When** the run reads past it,
   **Then** reads refuse and the truncation is disclosed rather than silently partial.
4. **Given** a run whose task scope excludes `author_file`, **When** it attempts one,
   **Then** it refuses even though the definition's ceiling permits it.

---

### User Story 3 — The proposer publishes what the analyzer contained (Priority: P1)

The analyzer finishes, checkpoints, and exits; the proposer starts, receives the contained
proposal, and opens it against the declared repository — holding the publishing credential the
analyzer never had.

**Why this priority**: The two-task split is 038's central safety property, and it has never
executed. Until it does, "the task holding the credential never holds the analysed content" is a
statement about a jobspec rather than an observed fact.

**Independent Test**: Run both tasks in sequence and confirm a proposal is opened carrying the
authored files, with the analyzer observably holding no credential.

**Acceptance Scenarios**:

1. **Given** a completed analyzer task, **When** the proposer runs, **Then** a proposal is opened
   and `PROPOSAL_OPENED` is recorded.
2. **Given** an interrupted publish, **When** the run revives, **Then** the observer determines
   whether the proposal exists rather than opening a second one.
3. **Given** the analyzer task, **When** it attempts to read the publishing credential,
   **Then** it cannot — it holds no attested identity that can.
4. **Given** the handoff, **When** it occurs, **Then** it is a continuation and **not** a resume:
   no resume attempt is consumed on a healthy run.

---

### User Story 4 — The gap cannot reopen (Priority: P2)

The capability ledger stops listing the authoring trio as deliberately unreachable, and the
suite that would have caught this earlier now covers the path that was missing.

**Why this priority**: The ledger already names these three against this feature as their record.
Leaving the entries in place after registering the tools would make the ledger assert something
false; removing them without replacing the coverage would leave the next capability to repeat the
same three-layer gap.

**Independent Test**: Delete the trio's ledger entries and confirm the sweep passes; then
un-register one tool and confirm the sweep fails.

**Acceptance Scenarios**:

1. **Given** the trio registered, **When** the ledger sweep runs, **Then** it passes with no
   `DELIBERATELY_UNREACHABLE` entry for any of the three.
2. **Given** a rigged tree where a registration is removed, **When** the sweep runs,
   **Then** it **fails** — a suite that cannot lose proves nothing.

---

### User Story 5 — Nothing that already worked has to be rewritten (Priority: P2)

038's existing rows keep passing unedited, and definitions that name no authoring tools behave
exactly as before.

**Why this priority**: The fixture toolset carries 008–012's lanes. A change to the one place
that answers "what can this platform do" reaches every run in the repository.

**Independent Test**: Run the full suite with no edits to 038's conformance files and confirm the
diff over them is empty.

**Acceptance Scenarios**:

1. **Given** the authoring rows as merged, **When** the suite runs, **Then** they pass unedited.
2. **Given** a definition naming no authoring tools, **When** it runs, **Then** its vocabulary,
   ceiling resolution and records are unchanged.

---

### Edge Cases

- A ceiling grants `author_file` to a definition that is dispatched **without** a subject mount —
  refused before the run starts, or refused at first read?
- A definition is granted `open_proposal` in the analyzer task, where no credential can be read:
  the refusal must name the missing authority, never surface as a publishing failure.
- `open_proposal` is attempted twice within one run — non-repeatable, observer-mediated.
- The analyzer authors nothing, then the proposer starts: an empty proposal must be refused
  rather than opened.
- Containment rejects every authored file: the run ends without a proposal, and says why.
- Two runs carry the same idempotency key: `branch_for` collides deliberately, and the second
  must not open a second proposal.
- The subject mount is the platform's own tree — already refused by `resolve_subject_mount`, and
  the row must survive registration becoming real.
- `target_repository` is unreachable, empty, or the credential is refused at clone time: refused
  before any workspace exists, naming the acquisition.
- The clone succeeds but the repository is enormous: the read budget already governs what is
  *read*, and the acquisition needs its own bound or an explicit statement that it has none.
- The repository moves between the clone and the publish, so the proposal's base no longer
  exists.
- An analyzer is killed mid-run and revived on another node, where the checkout path does not
  exist: the resume path re-acquires **at the recorded commit**, never at HEAD — a base that
  drifts between attempts would make two attempts of one run analyse two different trees.
- A run reaches terminal state with kept requests holding subject-derived content: scrubbed
  (FR-033), and a revival attempt after scrubbing cannot occur because only pending steps read
  arguments.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The authoring trio MUST be reachable by a dispatched run whose ceiling grants it —
  reachable meaning resolvable by name, callable through the governed pipeline, and refused by
  the ceiling rather than by the vocabulary when it is not granted.
- **FR-002**: A ceiling record naming any of the three MUST parse and resolve, so that
  `unknown_ceiling_entry` is reserved for genuinely unknown tools.
- **FR-003**: Registration MUST remain the opt-in switch: a definition whose ceiling omits an
  authoring tool MUST have no authoring, even though the registry knows the name.
- **FR-004**: Every authoring call MUST traverse the identical governed path other tools do —
  same entry, same hooks, same ceiling check, same records. **Argument provenance and risk class
  are the only permitted differences.**
- **FR-005**: The subject MUST be readable only through the governed read path, so the injection
  lens attaches, the read is recorded, the budget is countable, and what was consulted is
  enumerable.
- **FR-006**: `author_file` MUST write only into the run's workspace; any path escaping it MUST
  be refused, resolved rather than string-matched.
- **FR-007**: The analyzer task MUST hold no credential that could publish, and this MUST be
  observable as a property of the run rather than asserted by a comment.
- **FR-008**: The proposer task MUST receive a contained proposal and publish it without ever
  mounting the subject.
- **FR-009**: The handoff between the two tasks MUST be a checkpoint and continuation, and MUST
  NOT consume a resume attempt on a healthy run.
- **FR-010**: `open_proposal` MUST be non-repeatable with an observer, so an interrupted publish
  resolves rather than opening a second proposal.
- **FR-011**: The publishing credential MUST be read under the publishing task's own attested
  identity, per task, and never persisted.
- **FR-012**: A `write` cell MUST be qualified before any authoring runs, and an unqualified cell
  MUST stop the run with the reason recorded — distinguishable from a provider being unavailable.
- **FR-012a**: A **permanent** `write` cell MUST be qualified through the mechanical scorer
  (ADR-0063) and bound in the estate, so authoring is available rather than demonstrated. The
  qualification MUST be a governed act carrying its dated evidence, as every other cell's is.
- **FR-012b**: The qualified cell MUST be the model the estate already runs its live lane on, and
  MUST NOT be changed during this feature — a model swap mid-feature makes every measurement
  taken before it unusable as evidence for what shipped.
- **FR-013**: The authored content MUST NOT enter the audit trail; records carry paths, digests
  and provenance.
- **FR-014**: The tier's jobspec MUST actually execute the platform's entrypoint in both tasks,
  and a job that declares a task with nothing to run MUST fail a check rather than dispatch.
- **FR-015**: The capability ledger MUST no longer list the trio as deliberately unreachable.
  Because the trio registers **per run** (the handlers hold run-scoped state), the ledger's
  static sweep cannot observe the registration directly — so the entries MOVE to a declared
  per-run-reachable record naming the registrar, they do not vanish. The sweep MUST fail if a
  per-run-reachable entry's registrar stops registering it — kept honest by a row that drives
  the registering construction, not by the declaration alone.
- **FR-016**: At least one row MUST run **where dispatched work actually runs** — an enclave row
  under an attested workload identity, which fails rather than skips when the lane is
  unavailable.
- **FR-017**: 038's existing conformance rows MUST pass unedited, and the diff over them MUST be
  empty.
- **FR-018**: A row MUST exist that **fails** when registration is removed, so the suite proving
  reachability can lose.
- **FR-019**: The refusal reasons across the three layers — unknown tool, outside the ceiling,
  outside task scope — MUST be distinguishable, because each sends an operator to a different
  record.
- **FR-020**: `open_proposal` MUST publish against **real GitHub**, never a fixture. A fixture
  handler here would be ADR-0047's exact shape — the proposal is the tier's only externally
  visible output, so a fixture would make every row green forever while the feature did nothing.
- **FR-021**: The version-control integration MUST use **adopted vendor CLIs** — `git` for clone
  and push, `gh` for opening the proposal — pinned and provenance-checked like any other adopted
  content. No MCP server is introduced, so no additional operated component is added.
- **FR-022**: Version-control egress MUST occur in the publishing task only, never the analysing
  one, and only within that task's existing `github.com` allowlist. Cloning is the one exception
  and happens before dispatch, outside the tier entirely (FR-027).
- **FR-023**: The registry-review determination — that native CLI tooling is correct here and MCP
  is not — MUST be recorded with its reasoning, because Principle II makes the MCP-versus-native
  choice a determination rather than a default, and a determination made silently is what that
  clause exists to prevent.
- **FR-023a**: The installation token MUST reach the CLIs per invocation through the environment
  and MUST NOT be written to disk, a git config, a credential store, a checkpoint, or a log. The
  existing `InstallationToken.__repr__` redaction MUST hold across the subprocess boundary — a
  token that leaks through a traceback is one no logging policy would have caught.
- **FR-024**: The enclave row MUST open a real proposal against a real repository and MUST
  **fail rather than skip** when that lane or its App installation is unavailable — and per the
  constitution's Quality Gates, the contract MUST name the party responsible for running it.
- **FR-025**: A proposal opened by a row MUST be distinguishable from one opened by a person, and
  MUST NOT accumulate: repeated runs against the same idempotency key reuse the branch rather
  than opening a second proposal.
- **FR-026**: The subject tree MUST be a checkout of `target_repository`, produced by the platform
  before dispatch, so that the tree analysed and the repository published to cannot differ. The
  existing `resolve_subject_mount` refusal (`subject_is_platform_tree`) MUST continue to hold
  against the produced path.
- **FR-027**: The clone MUST happen in the dispatching context and MUST NOT occur inside the
  hardened tier — the analysing task keeps no credential and no egress, and acquiring the subject
  is not permitted to become the exception to that.
- **FR-028**: A failure to obtain the subject — repository unreachable, revision missing,
  credential refused — MUST refuse the request **before** anything is produced, carrying a reason
  that names the acquisition rather than surfacing later as an empty analysis.
- **FR-029**: The version-control host MUST be a named product with a probe, and the authoring
  platform tools MUST carry a product mapping, so a run suspended on an outage is revivable by
  the sweeper that watches products.
- **FR-030**: A platform tool that is suspendable and carries **no** product mapping MUST be
  refused or reported, rather than producing a suspension nothing can revive. The gap is general;
  the trio are only the first instance of it.
- **FR-031**: The proposal's description MUST carry the model's rationale **and** platform-authored
  provenance — correlation ID, what was consulted, content digests, and the truncation note when
  the read was partial. A proposal that reads complete while resting on a partial read MUST NOT
  be publishable, matching the refusal `compose()` already performs.
- **FR-032**: The rationale is model-authored text reaching a customer's repository, so it MUST
  pass the same containment the authored files do. A description is content, and exempting it
  because it is prose would leave the one field nobody scanned.
- **FR-033**: An authoring run's kept model requests MUST be scrubbed at the run's terminal
  state. 040 stores a model's stated arguments durably so an interrupted act can be repeated
  faithfully — and for `author_file` those arguments are file content derived from a customer's
  private repository, resting in the control plane. 040's own design makes this safe to scrub:
  resume reads arguments only for **pending** steps, so a terminal run's requests are read by
  nothing — and 040 deliberately left the request removable rather than load-bearing, which
  this requirement is the first to consume. FR-013's rationale extends here: the trail was
  refused a copy nobody can delete; the control plane holds one only while the run can still
  need it.

### Key Entities

- **Authoring trio**: `read_subject` (read), `author_file` (the registry's first write),
  `open_proposal` (write, non-repeatable, observer-required).
- **Trees**: the per-run subject (read-only) and workspace (read-write) pair that makes the
  file set unforgeable by paths.
- **Authored artifact**: the accumulating record of what was written — path, digest, whether it
  edited an existing subject file.
- **Proposal**: the composed, contained set of authored files plus the branch derived from the
  run's idempotency key.
- **Capability ledger**: the sweep of every defined capability against every reachable one, with
  a named record for each deliberate exclusion.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A ceiling granting authoring is accepted, where today it is refused — demonstrated
  by the same record failing before the change and resolving after.
- **SC-002**: A dispatched run completes an authoring cycle end to end: subject read, file
  authored, containment passed, proposal opened — with every step recorded under one correlation
  ID.
- **SC-003**: 100% of authoring calls traverse the governed entry; a rigged seam that skips it
  makes the assertion fail.
- **SC-004**: The analyzer task's inability to publish is observed, not argued — an attempt to
  read the publishing credential from it fails.
- **SC-005**: Zero edits to 038's conformance rows, measured as an empty diff.
- **SC-006**: The capability ledger reports zero unreachable authoring capabilities, and reports
  a failure when one is removed.
- **SC-007**: At least one row runs under an attested workload identity in the enclave and fails
  rather than skips when that lane is unavailable.
- **SC-008**: Every one of the three refusal layers is distinguishable by an operator reading
  only the record.
- **SC-009**: A real pull request exists on a real repository, opened by a dispatched run, and
  its contents match the authored artifact's digests.
- **SC-010**: Running the same authoring request twice yields one proposal, not two.
- **SC-011**: A `write` cell is qualified and bound, and a run whose cell is withdrawn stops with
  a governance reason rather than an outage one — both halves observed, not just the passing one.
- **SC-012**: A run interrupted by a version-control outage is revived by the sweeper rather than
  waiting indefinitely, and revival opens no second proposal.
- **SC-013**: A reviewer reading only the proposal can identify the run that produced it, what it
  consulted, and whether the read was partial.

## Assumptions

- **The trio stays product-blind.** Producing a file and publishing a proposal are the same act
  for every product, per ADR-0064. This feature adds no product knowledge to `core`.
- **The tier's jobspec is repaired, not redesigned.** Its mounts, identities, lifecycle and task
  scopes were carefully reasoned by 038 and are taken as correct; what is missing is the command
  each task runs.
- **One enclave row is the floor, not the ceiling.** The user's framing — at least one row where
  dispatched work runs — is treated as a minimum, and 040's `cpu_total_compute` repair is what
  makes the local enclave able to place these allocations at all.
- **The `write` cell already resolves.** `resolve_write_cell` landed with 038 and needs a
  qualified cell in the matrix, not a new resolver.
- **Registration stays per-run for the analyzer pair**, because both handlers hold run-scoped
  state (the workspace they may write to and the artifact they accumulate). This does not weaken
  the opt-in property, since the ceiling still decides.
- **The subject is produced, not supplied.** Clarified 2026-08-07: the platform clones
  `target_repository` and mounts the checkout. An intake surface where a *user* declares
  workspace, repo and scope is still the successor feature — this feature takes the repository
  from the authoring request an operator already authors.
- **`owned_repositories` remains the requester bound.** The App installation is granted to an
  organisation rather than an individual, so two requesters inside one organisation share one
  installation; `request.py` already records that this check alone bounds the requester. Cloning
  from `target_repository` inherits that bound rather than widening it.
- **No new standing credential.** ADR-0062's exception is used as written; this feature reads it
  and does not widen it.
- **A GitHub App installation on a maintainer-owned repository is an operator prerequisite**, not
  something this feature provisions. The enclave row needs somewhere real to open a proposal, and
  a row with nowhere to publish fails rather than skips.
- **`git` and `gh` are adopted, not authored**, and pinned like any other adopted content
  (Principle VIII). Both are already present in this repository's own toolchain, so the
  dependency is on versions rather than on availability.
- **Proposals opened by rows are disposable.** They land on branches derived from the run's
  idempotency key, on a repository that exists for this purpose, and nothing merges them.
