# Research: The admin console

Measured against `d30f771` plus this branch's spec commits. Where a measurement contradicted
the spec's framing, the contradiction is the entry.

## R1 — The gated write path has no deployed principal, and that is the feature's real first job

**Measured**: `authority_submit.py` posts to the fabric with `X-Vault-Token` **omitted when no
token was supplied**, and `service.py` constructs `VaultAuthoritySubmitter` without one. No
trust-fabric policy grants `create`/`update` on any `harness-authority` path. The
`authority_change` policy — the one carrying Control-Group write grants — is attached to **no
role** and is count-gated off in dev. The gated rows pass because they run with an operator
token.

So the spec's "a governed write path already exists" is true of the *code* and false of the
*deployment*: the request-and-decide mechanism has never had a principal that could exercise
it. This is 041's shape again — correct, tested, wired to nothing — one layer down.

**Decision**: 044 creates an `authority_submit` trust-fabric policy granting `create`/`update`
on exactly the records the console writes (`claim-mappings/*`, `ask-bindings`,
`product-connections`), with `control_group` blocks attached **when quorum is configured** (the
existing `control_groups_enabled` pattern), attached to the **api role**; the submitter runs
under the API's own attested identity, not a configured token. In dev (quorum null) the grant
is ungated and FR-023b requires the console to say so.

**Alternatives considered**: a dedicated console service identity (rejected — Principle VI, and
the API already authenticates the person; a second identity is a second thing to bound); the
operator token via env (rejected — a standing credential, Principle IV's exact shape).

## R2 — The console's write targets, and Q3's fix, named precisely

**Decision**: three record families are writable through the console, and `controlled_paths`
is extended to cover each (FR-023a):

| Record | Exists today? | Console operation |
| --- | --- | --- |
| `harness-authority/data/ask-bindings` | yes (026, +043's `relevance_cell`) | bind a qualified cell per source/role; the judge toggle (R4) |
| `harness-authority/data/claim-mappings/*` | yes (007) | grant/revoke roles — including creating the `admin` mapping itself |
| `harness-authority/data/product-connections` | **no — new** | TFE org/workspace, product-Vault address/namespace (R5) |

A unit scan (V-row) asserts every path the console can write appears in `controlled_paths`,
against the module's own list — the same completeness-by-scan shape as 042's V6.

**FR-023's answer, established**: the claim-mappings gap **is a defect** — the variable's
description promises gating the fabric never attached — and it is fixed by the same
`controlled_paths` extension rather than by a separate mechanism.

## R3 — Console operations are API routes serving the portal; MCP's absence is a row

**Measured**: the portal is a genuine thin client — `relay.py` is its only HTTP door, carries
the person's token, holds no credential; pages are server-rendered templates. MCP's operation
table (`transport.py`) is a dict the row can read.

**Decision** (Q1): new API routes under `/console/…` — configuration read, change request,
connection verify — required-role `admin`, consumed by portal pages (`/settings`) through the
existing relay. **No MCP operation**, and a row asserts the operation table contains no
configuration verb, turning the absence into a checked fact.

## R4 — The judge toggle lives in the ask-bindings record, which makes no-restart free

**Measured**: the surface already reads the ask-binding record **per ask**
(`resolve_relevance` → `read_binding()`), so a field in that record is picked up on the next
request with zero new plumbing — FR-013 satisfied by placement rather than by machinery. 043's
`Answer.relevance_note` already renders a gate note into responses, and `_record_relevance_gate`
writes `MODEL_GATE`.

**Decision**: `relevance_enabled: bool` on the ask-bindings record, **absent = enabled** so
every existing record keeps its meaning. When disabled: the surface skips resolution and
judging, the answer carries a visible disclosure in `relevance_note`
("relevance was not checked: disabled by an administrator"), and the record carries a
disposition distinguishing `relevance_disabled_by_admin` from `relevance_unavailable`
(FR-012 — the two send a reader to a person's decision and to an outage respectively). The
`MODEL_GATE` event is **not** written when disabled — the gate did not run, and a gate event
for a gate that did not run is the vacuous-assertion shape 040 caught in M9.

**Alternative considered**: a separate `gate-toggles` record (rejected for now — a second
record read per ask adds a fabric read to every answer, and the binding record is already the
authority on how answering is configured; revisit when a second toggle exists).

## R5 — Product connections are a NEW record, and honesty about consumers is the design

**Measured**: **nothing in `src/` or `infra/modules/` configures TFE at all** — no
organisation, no workspace, no broker implementation; the Terraform pack's handlers are
fixtures. The product Vault's address is `VAULT_ADDR` in jobspecs — assembly, not a governance
record.

So Q4's scope includes a record with **no existing consumer**. FR-022 says settings the
platform does not implement must be absent; the resolution is that 044 implements the
setting's *function* narrowly and states it:

**Decision**: `product-connections` holds `{tfe: {address, organization, workspace}, vault:
{address, namespace}}` — locations only, **never credentials** (FR-018b). Its consumers in
044 are exactly two, and the console says which: (1) the **verification probe** (FR-018c) —
an unauthenticated reachability check (TFE's `/api/v2/ping` equivalent and Vault's
`sys/seal-status`-shaped health endpoint), whose result is displayed as
`verified / unreachable / unverified`, never folded into "applied"; (2) **display with
provenance**. Consumption by the packs' tool clients is the Terraform leg's work and the
record says so in the console — a labelled "not yet consumed by dispatched runs" is FR-022's
honest middle, distinct from inventing a setting.

**Alternative considered**: wiring the vault pack's handlers to read the record per call
(rejected — it puts a fabric read in every tool invocation to serve a record nothing needed
yet, and quietly moves assembly configuration into governance without its own argument).

## R6 — The admin role rides the mechanism that already exists, disjointly

**Measured**: `TokenVerifier` resolves roles from claim mappings read back from the fabric;
`ROLE_VISIBILITY` is a dict keyed by role; the mappings **route** already exists and submits
through the gated path.

**Decision** (Q2, FR-016/016a/017): `admin` becomes a third `ROLE_VISIBILITY` key mapping to
`frozenset()` — **no audit visibility by virtue of being admin** — and console routes require
the role by checking the resolved subject, exactly as evidence reads check theirs. The role is
granted by writing a claim mapping through the **existing** gated route; the console offers no
path to write a mapping whose role is `admin` for the requester's own subject (FR-017), and a
row drives exactly that attempt. Nothing new is built for role creation — the feature's claim
is that the existing mechanism suffices, proven by using it.

## R7 — The role vocabulary is presented, not widened

**Decision** (FR-018): the console presents ADR-0039's real names — `ask / plan / write /
judge / summarize` — each with a one-line description ("judge — scores and validates other
models' outputs", "ask — answers questions, including research against the corpus"). The
proposed `research` and `validate` names are **dropped, not mapped**: a display alias invites
the reader to believe a capability exists that does not, and no ADR is amended because no new
capability is being named. Recorded in the plan's Complexity row because it declines half of
the original ask's vocabulary, deliberately.

## R8 — Reads are the API's own; writes are the person's request

**Decision**: configuration **reads** run under the API's existing fabric identity
(`harness_authority_read` already covers every record but the new one — extended with the
exact-path lesson from 042: `product-connections` gets its own line, no glob). Reads are
recorded with a new `CONFIG_READ`-shaped audit event carrying the administrator and the
records viewed, on the EVIDENCE_READ precedent ("evidence access is itself audited").
**Writes** go through `authority_submit`'s three-outcome mapping, generalised from
`ClaimMapping` to a `ConfigChange` (record path + payload + requester) — the module keeps its
007-era truthiness lesson (`wrap_info` present-as-null on every response).

## R9 — Concurrency and provenance ride KV v2, not new machinery

**Decision** (FR-019/020, US5): every console write is CAS-guarded (`cas` = the version the
administrator read), so two concurrent edits surface as "the record moved" rather than a
silent overwrite — the same reasoning `vault_write` recorded for its own `cas`. Provenance:
the console writes a `set_by: console/<subject>` field into the record payload; a record
written by Terraform lacks it (or carries the module's marker), so "last set by" is readable
from the record itself and no second store exists to disagree. An estate apply overwriting a
console change is **visible** (version bump + provenance flip) — satisfying "observable rather
than silent" without fighting Terraform for ownership.

## R10 — The a11y lane walks the new page

**Measured**: `tests/a11y/test_wcag.py` visits `/`, a thread, and delete confirmations — a new
page is covered by none of them (FR-021b's finding). **Decision**: the suite gains `/settings`
rows in both files (WCAG scan + keyboard/screen-reader), behind the same authenticated-page
fixture the thread rows use.

## R11 — What 044 does not build

- **No approval UI.** Approvals happen in Vault (ADR-0016); the console shows *pending* and
  who can approve, never an approve button. Building one would move the quorum into the
  surface that requests — the fox designing the henhouse door.
- **No new eval lane** — no model output is produced by this feature.
- **No MCP or API-public verbs** (Q1); no second write mechanism; no credential entry
  (FR-018b); no widening of ADR-0039 (R7).
- **No pending-change withdrawal** in the first cut: a wrapping token expires on its own TTL,
  which is Vault's native withdrawal; the console displays the expiry. Recorded as the
  deferred lifecycle answer from clarify.

## R12 — ADR: one new record

**ADR-0069 — governance configuration is requested at a console and decided by the trust
fabric** (Proposed). It records: the deliberate move of the governance/assembly line that 026
drew (deployment config was rejected; a *gated, recorded, person-originated* request path is
the argued exception); the disjoint admin role; the disclose-not-suppress toggle semantics as
the template for every future toggle; and R1's finding that the request-and-decide mechanism
predated any principal able to use it.
