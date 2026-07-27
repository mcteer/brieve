# Tasks: Northbound API

**Input**: Design documents from `specs/008-northbound-api/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**The premise, checked before anything else**: this feature adds the first new runtime
dependencies since 005. T001 runs the license gate against them **before** anything is
built on top. This repository has already had a dependency refused after the design assumed
it — psycopg, LGPL-3.0-only, rejected twice over — and the cost of finding out late is
every task that imported it. Cheap to check, expensive to skip.

**Tests**: the OIDC provider is the **only** fake, because it is the only component outside
our boundary — we do not deploy the customer's identity provider. Everything else runs for
real: real Vault, real Postgres, real allocations. The double must sign real JWTs with a
real key; one that returns a pre-baked subject would leave this feature's central guarantee
unproven while every test passed.

**Scope bound**: the surface adds no decision of its own. If a route starts deciding
something rather than asking the core, that is the signal Principle II is slipping — stop
and say so rather than adding a second authorization path.

**Organization**: grouped by user story so each is independently verifiable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Include exact file paths in descriptions

## Gate Task Types *(mandatory when applicable)*

| Gate type | When required | What the task must prove |
| --- | --- | --- |
| **Fail-closed** | Absent, expired, unverifiable, or unmapped identity; IdP unreachable | Refused with **zero executions** — not refused after something ran |
| **Conformance** | Every row in `contracts/conformance-api.md` | Fifteen rows; seven need the enclave and fail loudly without it |
| **Correlation / evidence** | Every operation, and every evidence read | Identity present in every record for the correlation ID; one meta-audit record per read |
| **Eval** | N/A | No packs, prompts, models, or policies promoted |
| **No-secret-leak** | Audit records, logs, spans, the description | No token material, no JWKS private half, no credential in any emitted artifact |
| **Determinism** | Every test path | The OIDC double is the only fake. No live model, no live managed-product API |

## Path Conventions

- Surface: `src/surfaces/api/` (token verification, routes), `src/surfaces/dispatch/`
- Core: `src/core/audit/` (evidence store, sealed-core changes), `src/core/identity/` (identity flows — sealed core per Principle V)
- Trust fabric: `infra/modules/trust-fabric/database.tf`
- Tests: `tests/unit/`, `tests/component/`, `tests/conformance/api/`, `tests/harness/`

---

## Phase 0: Premise Gate

- [ ] T001 [GATE:conformance] Add `fastapi`, `uvicorn`, `pyjwt[crypto]` to a scratch environment and run `bash scripts/check-licenses.sh`; assert every reported license clears `licenses/allowlist.txt` and none matches the `GPL|AGPL|BUSL|SSPL` second belt. **Everything after this depends on it.** If any is refused, stop and revisit research.md D1/D2 rather than weakening the gate — that trade is backwards, and the repository has already made the right call once

---

## Phase 1: Setup

- [ ] T002 Add the `surfaces` optional-dependency group to `pyproject.toml` with exact pins for `fastapi`, `uvicorn`, and `pyjwt[crypto]`, carrying a comment stating why these are an **extra** and not base: `src/core` must not acquire a web framework in its install (Principle I), unlike `pg8000`, which core itself imports
- [ ] T003 Add `--extra surfaces` to `UV_RUN` in `Makefile` so no gate can run in an environment that silently lacks the surface, matching the reasoning already recorded for `--extra adapters`
- [ ] T004 [P] Confirm `fastapi`, `uvicorn`, and `pyjwt` ship `py.typed`; add a `mypy` override in `pyproject.toml` **only** for any that does not, with a comment naming which. If all are typed, record that and add nothing — an override for a typed package silently weakens `strict`
- [ ] T005 [P] Create `src/core/identity/__init__.py`, `src/surfaces/api/__init__.py`, and `src/surfaces/dispatch/__init__.py`, and extend `src/surfaces/__init__.py` beyond its stub docstring. `src/core/identity/` is a new package and T016/T017 write into it — under `mypy` strict with `explicit_package_bases`, a missing `__init__.py` is a build error rather than an inconvenience

---

## Phase 2: Foundational — the store, the seam, and the subject

**Blocking for every user story.** Three things the spec assumes and the codebase lacks
(plan.md): there is no durable audit store, no tenant, and no way to start a run from
outside a Python process.

The evidence store lands here rather than under US4 because it is **core, not surface** —
the trail belongs to the platform whether or not anyone reads it over HTTP. US4 builds the
governed *read* of it; this phase builds the thing being read.

### Sealed core (security-maintainer review required)

- [ ] T006 Add `EVIDENCE_READ` and `EVIDENCE_READ_REFUSED` to `AuditEventType`, and `EvidenceDisposition` (`SCOPED` / `OUT_OF_SCOPE`), in `src/core/audit/schema.py`. Additive — nothing renamed, nothing removed. `EvidenceDisposition` belongs here rather than in a surface because it types a field on a record written to the core trail
- [ ] T006a Add `tenant_id` to `AuditEntry` in `src/core/audit/schema.py` and to `compute_entry_hash` in `src/core/audit/chain.py`, so the bounding dimension is **covered by the chain**. This **changes the shape of a sealed seam** and is not additive — the earlier plan said otherwise and was wrong. A `tenant_id` column outside the hash would leave the field deciding who may see a record alterable without breaking the chain
- [ ] T006b Add a tenant resolver in `src/core/identity/tenant.py`: the authenticated subject's claim where a surface established one, otherwise a **configured default tenant**. Required before T006c — `start_governed_run` is reached from `src/adapters/pydantic_ai/agent.py` and from the 002–007 suites, none of which has an identity provider, so a required `tenant_id` with no source would stop the adapter starting a run at all
- [ ] T006c Update `build_next_entry`, `InMemoryAuditSink`, `start_governed_run`, and every existing caller in `src/core/`, `src/adapters/`, and `tests/` to carry `tenant_id` from the resolver. **No data migration is required** — audit has only ever existed in memory, so no persisted entry has a hash computed the old way. Say so in the commit, because that will not be true for the next such change
- [ ] T007 Create the `EvidenceQuery` protocol and `EvidenceQueryRequest` in `src/core/audit/query.py`, with **no `append` method**. Not "append raises" — no append. `AuditSink` in `sink.py` keeps its shape unchanged
- [ ] T008 [P] Add a unit test in `tests/unit/test_evidence_query_is_read_only.py` asserting `EvidenceQuery` exposes no method that writes, by inspecting the protocol rather than by convention

### The durable evidence store

- [ ] T009 Create `src/core/audit/evidence_schema.sql` with the `audit_entries` table and the `audit_by_tenant_time` index per data-model.md. `tenant_id` on the row, not joined — the bounding dimension must live on the record being filtered
- [ ] T010 Implement `PostgresAuditSink` in `src/core/audit/postgres_sink.py` against the `AuditSink` protocol, drawing credentials through `core.durability.credentials` exactly as the durability provider does. No code path may accept a DSN carrying a password
- [ ] T011 [GATE:conformance] Verify in `PostgresAuditSink.append` the same chain invariants `InMemoryAuditSink` enforces — sequence, `prev_hash` linkage, `entry_hash` recomputation — so integrity is a property of the entry rather than of the store holding it
- [ ] T012 [P] Add a component test in `tests/component/test_audit_sink_parity.py` asserting both sinks accept the same valid entry and reject the same malformed one. Two implementations that disagree about validity are two audit schemas
- [ ] T013 Implement `PostgresEvidenceQuery` in `src/core/audit/postgres_query.py` — a **separate module**, holding a separate connection drawn from the evidence role, importing nothing from `postgres_sink.py`. Separate modules rather than one file so "the query cannot reach the sink" is a property of the import graph rather than of everyone in the same file being careful
- [ ] T014 [GATE:no-secret-leak] Add the evidence dynamic role to `infra/modules/trust-fabric/database.tf` granting **`SELECT` only** on `audit_entries` — not `ON ALL TABLES`, which would also expose durability's checkpoints. Comment that this is defence #2 and holds regardless of what the Python does (ADR-0035, research.md D5)
- [ ] T014a Apply `evidence_schema.sql` from `infra/bin/enclave-up`, using the **run role** (the only one holding `CREATE ON SCHEMA public`), **before** the evidence role issues its first credential. Naming an owner matters: `creation_statements` referencing `audit_entries` fail outright if the table does not exist yet, so credential issuance breaks rather than degrades — and an ordering requirement nothing owns is a comment. Add `ALTER DEFAULT PRIVILEGES` so later tables do not silently escape the grant
- [ ] T014b Extend `infra/bin/enclave-verify` to assert the evidence schema is present and the evidence role can `SELECT` it, so `make dev-up`'s exit contract covers the evidence store the way it already covers durability
- [ ] T015 [GATE:conformance] Add an enclave test in `tests/conformance/api/test_evidence_role_cannot_write.py` attempting `INSERT`, `UPDATE`, and `DELETE` on the evidence connection and asserting **Postgres** refuses each. Marked `enclave`; fails loudly when absent rather than skipping

### The authenticated subject and the tenant dimension

- [ ] T016 Create `AuthenticatedSubject` and `SubjectKind` in `src/core/identity/types.py` per data-model.md, with `tenant_id` required — a subject with no tenant refuses rather than defaulting, because defaulting it would default it to something. **In core, not in a transport**: Principle V names identity flows as sealed core, and a type defined inside the first transport would make the second import it or duplicate it
- [ ] T017 [P] Create the claim-to-role mapping in `src/core/identity/claims.py` — pure data-to-roles with no dependency on how a token arrived, so every transport shares it. An **empty role set means refuse**; an unmapped claim is not a default role (FR-006)

### The dispatch seam

- [ ] T018 Create the `RunDispatcher` protocol in `src/surfaces/dispatch/types.py` returning a `RunHandle` of `run_id` and `correlation_id` only. Nothing naming an allocation, container, or scheduler — the caller must not learn the substrate any more than the surface does
- [ ] T019 [P] Implement `InProcessDispatcher` in `src/surfaces/dispatch/inprocess.py` for hermetic tests
- [ ] T020 Implement `NomadDispatcher` in `src/surfaces/dispatch/nomad.py`, submitting a jobspec the way `infra/bin/enclave-conformance` already does. **Not optional**: Nomad is inside our boundary, and a run-start path proven only against a double has not been proven

### The application and the double

- [ ] T021 Create the app factory in `src/surfaces/api/app.py`. **Routes are registered here and nowhere else**, so the route-walking checks in US3 and US5 have one place to enumerate
- [ ] T022 [GATE:determinism] Create `tests/harness/fake_oidc_provider.py` issuing **real signed JWTs from a real generated key**, serving a real JWKS document, and supporting expired, wrong-issuer, wrong-audience, and bad-signature tokens. A double that skips signing would leave FR-004's guarantee untested while every test passed

**Checkpoint**: the store exists, the seam exists, the subject exists. User stories can now proceed in parallel.

---

## Phase 3: User Story 1 — A person authenticates as themselves, and stays themselves (P1) 🎯 MVP

**Goal**: the authenticated identity becomes the subject of authority manufacture, tool
calls, and every audit record for that correlation ID.

**Independent test**: authenticate against the double, invoke an operation, assert the
subject appears in the manufactured authority and in every audit record for that
correlation ID.

- [ ] T023 [US1] Implement OIDC token verification in `src/surfaces/api/verification.py` using `PyJWKClient` — signature, issuer, audience, `exp`, and `nbf`, with the algorithm **pinned** rather than read from the token header
- [ ] T024 [US1] [GATE:fail-closed] Refuse absent, expired, and unverifiable identities in `src/surfaces/api/verification.py` with **nothing executed** — the refusal must precede any core call, not follow one
- [ ] T025 [US1] [GATE:fail-closed] Refuse claims mapping to no role via `src/core/identity/claims.py` (FR-006), asserting in `tests/component/test_api_refusal_kinds.py` the refusal is distinguishable in audit from a failed signature — an operator debugging an integration needs to tell "your token is bad" from "your claim is not mapped"
- [ ] T026 [US1] Wire the verified subject into `start_governed_run` as `subject_user_id` in `src/surfaces/api/runs.py`, unchanged and untranslated
- [ ] T027 [US1] Implement `POST /runs` and `GET /runs/{run_id}` in `src/surfaces/api/runs.py`, returning a `RunHandle` through the dispatcher. **Never blocks** (FR-007a)
- [ ] T028 [P] [US1] [GATE:correlation] Component test in `tests/component/test_api_subject_is_root.py`: the authenticated subject appears in the manufactured authority and in **every** audit record for the correlation ID — every, not the first
- [ ] T029 [P] [US1] [GATE:conformance] Conformance rows in `tests/conformance/api/test_identity_rows.py` for identity-is-the-subject and fail-closed-on-identity, plus self-verifying break fixtures per 004's pattern
- [ ] T030 [US1] [GATE:conformance] Enclave row in `tests/conformance/api/test_run_start_does_not_block.py`: start a run outlasting the request and assert the response returns with a handle while it still executes. Response time unrelated to run duration
- [ ] T031 [P] [US1] [GATE:no-secret-leak] Add `tests/component/test_api_no_secret_leak.py` asserting no token, JWKS private material, or authorization header value reaches any audit record, span, or log line

**Checkpoint**: US1 alone is the MVP — a governed run can be started by a verified human whose identity is the subject of everything that follows.

---

## Phase 4: User Story 2 — There is no API key to steal (P1)

**Goal**: no static credential exists to find, because none is issued or accepted.

**Independent test**: enumerate every authentication path; assert none accepts a
platform-issued long-lived credential and that a machine caller authenticates by federated
workload identity.

- [ ] T032 [US2] Implement workload identity federation in `src/surfaces/api/verification.py`, exchanging the attested identity the way `core.durability.credentials` already does rather than inventing a second exchange
- [ ] T033 [US2] [GATE:no-secret-leak] Add `tests/unit/test_no_static_credentials.py` enumerating every authentication path and asserting what is **absent**. Strip comments before matching, following 007's `test_no_run_interrupt.py` — prose about API keys is not an API key, and this repository has already twice had a check match a comment
- [ ] T034 [P] [US2] [GATE:conformance] Conformance row for no-static-credential in `tests/conformance/api/test_no_static_credential.py`, with a break fixture that **adds** a static-key path and asserts the check catches it
- [ ] T035 [P] [US2] Extend `tests/unit/test_no_static_credentials.py` to assert there is no supported configuration creating a static credential — no settings field, no environment variable, no Terraform input

---

## Phase 5: User Story 3 — An API operation cannot bypass governance (P1)

**Goal**: the API exposes no direct tool invocation, and every tool call a started run makes
reaches the governed path.

**Independent test**: walk the application's registered routes; assert none reaches a tool
body.

- [ ] T036 [US3] [GATE:conformance] Implement the route-walking check in `tests/conformance/api/test_no_tool_route.py`, enumerating routes from the app object and inspecting what each reaches. **Not a text search** — a grep passes a docstring mentioning `invoke_tool` and misses a route reaching a tool through an alias
- [ ] T037 [US3] Break fixture in `tests/conformance/api/test_no_tool_route.py` registering a route that reaches a tool **through an alias**, asserting the check catches it. A fixture using the literal name proves only that the literal name is caught
- [ ] T038 [P] [US3] [GATE:conformance] Assert in `tests/component/test_api_denied_operation.py` that a denied operation executes nothing and the denial is audited
- [ ] T039 [P] [US3] Component test in `tests/component/test_api_reaches_governed_path.py` asserting a run started through the API reaches tools through `core.tools.invoke` with hooks intact — the governed path is the same one, not an equivalent one

---

## Phase 6: User Story 4 — Someone can read the audit trail, bounded by what they may see (P1)

**Goal**: the governed read path, scope-bounded, incapable of mutation, and audited in turn.

**Independent test**: query as two identities with different entitlements; assert each sees
only its own scope and neither can widen it.

- [ ] T040 [US4] Implement `GET /evidence` in `src/surfaces/api/evidence.py`. **`tenant_id` comes from the subject, never from the request** — the field does not exist on the request model, so widening is not a check that could be written wrong but a parameter that does not exist
- [ ] T041 [US4] Bound results by the querying subject's entitlements using the existing scope algebra in `core.authority.intersection`, not a parallel ACL. ADR-0035's "scope algebra rather than per-persona interfaces" is the machinery Principle IV already uses
- [ ] T042 [US4] [GATE:correlation] Write one `EvidenceAccessRecord` per read — who, when, query shape, result count, disposition — recording the **query shape, never the rows returned**, which would copy evidence into the record describing it
- [ ] T042a [US4] [GATE:correlation] Write the record to the **evidence-access stream** `evidence-access:{tenant_id}` in `src/surfaces/api/evidence.py`, naming what it read in `read_correlation_ids` (FR-010a). Both single-sided designs fail: appending to the queried run's chain lets reading evidence write into the evidence being read, and a freshly minted ID per read makes each record a chain of one — `seq == 0` takes `GENESIS_PREV_HASH`, so it links to nothing and can be deleted undetected. A stable per-tenant stream gives tamper-evidence without touching any run's chain
- [ ] T042b [US4] [GATE:conformance] Assert in `tests/conformance/api/test_evidence_stream_chains.py` that consecutive evidence-access records chain to their predecessor and that **removing one is detectable**. Break fixture writes each record under a fresh correlation ID and asserts the check catches the unchained singleton — the arrangement this task exists to prevent
- [ ] T043 [US4] Set `disposition` to `SCOPED` or `OUT_OF_SCOPE`. Both cases return zero rows to the caller; only the trail distinguishes them, because telling the caller would leak the existence of what they may not see
- [ ] T044 [P] [US4] [GATE:conformance] Enclave row in `tests/conformance/api/test_evidence_scope.py`: two identities with differing entitlements each bounded by their own scope, zero leakage across the boundary
- [ ] T045 [P] [US4] [GATE:conformance] Enclave row in `tests/conformance/api/test_evidence_zero_rows.py`: a cross-tenant attempt and a legitimately empty query both return zero rows and are distinguishable **in the trail**. **Construct the reachable attempt** — narrow by a `correlation_id` or `run_id` belonging to another tenant, since the request exposes no tenant parameter. A row written against a tenant parameter would assert something unreachable and pass regardless of behaviour. Break fixture makes both dispositions identical and asserts detection; one comparing row counts would pass against a broken implementation
- [ ] T046 [P] [US4] [GATE:conformance] Enclave row in `tests/conformance/api/test_evidence_meta_audit.py`: every read produces **exactly one** meta-audit record regardless of rows matched. Assert reading the meta-audit records terminates rather than compounding
- [ ] T047 [US4] Break fixture in `tests/conformance/api/test_evidence_role_cannot_write.py` handing the evidence path a **writable** connection, asserting the mutation is still caught by the database grant. A fixture that only removes the Protocol's type hint tests defence #1 and leaves #2 unproven
- [ ] T048 [P] [US4] Assert in `tests/component/test_evidence_has_no_verdict.py` that the read path returns records and carries no verdict field — the platform surfaces evidence with citations, never a judgment about what it means (ADR-0035)

---

## Phase 7: User Story 5 — The API is describable enough to compare against (P2)

**Goal**: an operation set recorded well enough that a second transport compares against
something written down.

**Independent test**: assert every exposed operation appears in a generated description, and
that adding one without recording it is detected.

- [ ] T049 [US5] Generate the operation description from the app in `src/surfaces/api/description.py`, deriving it from the same signatures and Pydantic models that validate requests
- [ ] T050 [US5] Commit a snapshot of the operation set and its dispositions to `specs/008-northbound-api/contracts/operations.snapshot.json`
- [ ] T051 [US5] [GATE:conformance] Add a snapshot diff check in the shape `enclave-digest-diff` uses, so an operation added without updating the snapshot fails. Generation alone does not satisfy SC-010 — a new route would simply appear, silently
- [ ] T052 [P] [US5] [GATE:no-secret-leak] Assert in `tests/unit/test_description_no_leak.py` that the description exposes no internal path, credential field, or scheduler detail

---

## Phase 8: Requirements no user story owns

Three requirements arrived from clarification and edge cases without landing in a story.
Grouped here rather than attached to an unrelated one, so nothing is covered by accident.

- [ ] T053 [GATE:fail-closed] Implement JWKS caching with a **bounded TTL** in `src/surfaces/api/verification.py`, and assert in `tests/unit/test_idp_unreachable_fails_closed.py` that a cold or expired cache against an unreachable provider refuses (FR-016). Keys are public verification material and may be cached; **identities are never honoured past their own `exp`** (research.md D3)
- [ ] T054 [GATE:conformance] Add `tests/unit/test_surface_never_pauses.py` asserting no path in `src/surfaces/` pauses, interrupts, or blocks a run (FR-015). Strip comments before matching, as T033 does
- [ ] T055 Implement `POST /claim-mappings` in `src/surfaces/api/mappings.py`, routing through `core.authority.changes` and returning **pending, not denied** (FR-013). A client seeing a refusal stops asking, so a change approved minutes later is never collected — 007's docstring already names this trap
- [ ] T056 [GATE:conformance] Enclave row in `tests/conformance/api/test_claim_mapping_gated.py` asserting a mapping change returns pending and takes effect **only on approval**, against the real Control Groups rather than a fake

---

## Phase 9: Polish

- [ ] T057 Wire `tests/conformance/api` into `make conformance` and confirm the enclave-marked rows **fail loudly when the enclave is absent** rather than skipping — a test that skips itself reports the same green as one that ran
- [ ] T057a Change `conformance-hermetic` in `Makefile` to exclude by **marker** (`-m "not enclave"`) rather than by path. `--ignore=tests/conformance/durability` sufficed while every enclave row lived in one directory; `tests/conformance/api/` holds both kinds, so as-is the fork-safe CI lane would collect the enclave rows and **fail on the merge commit**. Verify by running `make conformance-hermetic` with the enclave stopped
- [ ] T058 [P] Update `ROADMAP.md`: 008 lands; the four-transport parity row **stays Deferred**. Updating it now would be the stub FR-014 refuses
- [ ] T059 [P] Record the fifteen rows in force in `contracts/conformance-api.md` as **In force** rather than Planned, and confirm the named responsible party for the seven enclave rows is present (constitution v1.1.0)
- [ ] T060 [P] Update `AGENTS.md` so the harness runs `make conformance` before merging anything touching `src/surfaces/` or `src/core/audit/`
- [ ] T061 Run `make check` and `make conformance` against a live enclave, and confirm every break fixture passes on a clean tree — a row whose failure nobody has observed is a row nobody knows works

---

## Dependencies

```text
T001 (license gate)
  └─> Phase 1 (T002–T005)
        └─> Phase 2 (T006–T022, incl. T006a–T006c, T014a/T014b)  ← blocking for every story
              ├─> US1 (T023–T031) 🎯 MVP
              ├─> US2 (T032–T035)
              ├─> US3 (T036–T039)   [needs T021's single registration point]
              ├─> US4 (T040–T048)   [needs T009–T015]
              └─> US5 (T049–T052)   [needs T021]
                    └─> Phase 8 (T053–T056)
                          └─> Phase 9 (T057–T061)
```

**T001 gates everything.** If the license check refuses a dependency, every task after
Phase 1 is built on a package that cannot ship.

**Within Phase 2, two chains run and must not be interleaved carelessly:**

- **T006 → T006a → T006b → T006c** — the sealed-core change. `tenant_id` on `AuditEntry` and
  inside `compute_entry_hash` breaks every existing caller until T006c lands, so the tree is
  red in between. T006b (the resolver) must precede T006c, or there is nothing for the
  adapter and the older suites to supply. Land the four together rather than across commits.
- **T009 → T010 → T013 → T014 → T014a → T014b → T015** — schema, sink, read object, grant, applying
  the schema before the first credential, then the proof the grant holds. T014a sits where it
  does because the grant statement fails outright if `audit_entries` does not exist yet.

The rest of Phase 2 parallelises.

### Parallel example after Phase 2

```text
# Developer A: US1 identity path and run start (the MVP)
# Developer B: US4 evidence read path — the largest story
# Developer C: US2 + US3 negative assertions and route walking
# Developer D: US5 description and snapshot
```

---

## Implementation Strategy

### MVP (User Story 1 only)

Phases 0–2 plus US1. A verified human starts a governed run through HTTP and their identity
is the subject of everything downstream. That is the root of the delegation chain, and
nothing else in this feature matters if it is wrong.

Phase 2 is unavoidably large for an MVP because the evidence store and the dispatch seam are
prerequisites rather than features. That is the honest shape of a feature whose spec assumed
infrastructure that did not exist.

### Incremental delivery

1. **US1** — identity is the subject. Merge-worthy alone.
2. **US2 + US3** — the negatives. Cheap once US1 exists, and they close the two paths that
   grow quietly: a static key someone adds for convenience, and a route that reaches a tool
   directly.
3. **US4** — the evidence read path. The largest story, and the one that needs the enclave.
4. **US5 + Phase 8** — the description and the unowned requirements.

### Notes

- **The parity row is not in this feature.** Fifteen rows land; the four-transport parity
  row stays owed until a second transport exists (FR-014). A task claiming it would be the
  stub ADR-0047 forbids.
- **Sealed core changes (T006, T006a, T006b, T006c, T007) need security-maintainer review, and one
  of them is not additive.** T006a changes the shape of `compute_entry_hash`, which is the
  guarantee every other claim is reconciled against. The plan originally called all of this
  additive; the analyze pass showed it could not be, since the evidence table required a
  `tenant_id` that `AuditEntry` had no field for. The cheaper fix — a column outside the hash
  — would have left the field deciding who may see a record alterable without breaking the
  chain. No migration is needed only because audit has never been persisted; that is luck of
  timing, not a property to rely on again.
- **Six rows need the enclave and no CI check runs them.** Named to the agent harness in
  `contracts/conformance-api.md` per constitution v1.1.0. Same gap 005 recorded, unchanged
  in character and not closable by this feature.
