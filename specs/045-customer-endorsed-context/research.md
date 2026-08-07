# Research: Customer-supplied context

Measured against `d6be271` plus this branch's spec commits. Where a measurement contradicted
the obvious design, the contradiction is the entry.

## R1 — FR-022's answer: a second, parallel corpus — never a tenant dimension on the pin

**Decision**: customer content is its own corpus — an `EndorsedCorpus` with the same
`resolves(path, anchor)` contract — and the answering path consults the two through one
combined view. `load_corpus()` and everything behind it is untouched.

**Rationale**: the two corpora differ on every axis that matters. The pinned corpus is
process-wide, vendored through the repository, vetted by the supply chain (ADR-0004), and
identical in every deployment (Principle VII). Customer content is per-deployment, arrives at
runtime, and is trusted by *endorsement* rather than by review. A `tenant_id` parameter
threaded through `load_corpus` would make one reader serve two trust models, and every check on
the pinned side would need a branch for the endorsed side — which is precisely how "extending
resolution weakens the gate for the corpus too" happens.

**The combined view is a composition, not a merge**: resolution tries the pin, then the
endorsed set; a path can only ever live in one because of R2's namespace. US6's rows (the
pinned corpus unchanged) pass by construction — the old reader is not edited.

**Alternatives considered**: a tenant dimension on `Corpus` (rejected above); customer
documents appended into the platform manifest (rejected — one digest would then cover content
with two different trust stories, and the supply-chain scan would either cover customer
content, which is wrong, or exempt part of its own manifest, which is worse).

## R2 — Citations into customer content live under `/endorsed/<source>/…`, and provenance falls out of the path

**Decision**: every citable customer document gets a path under a reserved `/endorsed/`
namespace — `/endorsed/<source-name>/<relative-path>#<anchor>`. Provenance-per-citation
(clarify Q2) is then derivable *and still emitted as an explicit field* on each citation:
`provenance: "validated-design" | "customer-endorsed"`.

**Rationale**: the namespace makes collision with corpus paths structurally impossible (no
validated-design path begins `/endorsed/`), gives FR-013 its "every citation resolves against a
recorded pin or not at all" cleanly, and gives the renderer and the trail the same fact without
parsing. The explicit field exists because deriving provenance from a path prefix in every
consumer is a convention, and 038's payload table records what conventions become.

## R3 — Storage: Postgres, because customer content cannot live in the repository tree

**Measured**: `corpus-sync` writes into `corpus/` **in the repository** — vendored, reviewed,
shipped. Customer content arrives at runtime in a deployment; there is no repo commit, and
allocation filesystems do not survive rescheduling.

**Decision**: synced customer content lives in the harness Postgres — the durable store the
platform already operates (Principle VI: no new component) — as manifest rows plus document
sections, **content-addressed by version**: each adoption writes a new immutable version and
leaves prior versions in place. The endorsed *governance* record (who endorsed what, which
version is adopted) lives in the trust fabric like every other governance record; the *content*
lives in Postgres like every other bulk artifact. Governance in Vault, weight in Postgres — the
same split the audit plane already uses.

**Retention of superseded versions is deferred and recorded** (like 040's kept-requests): a
version is only unreferencable once no run record cites it and no suspended run pins it, so
deletion is a decision with a query behind it, not a TTL. Versions are kept until a successor
feature decides; the record is removable rather than load-bearing.

## R4 — Run isolation rides the version, and resume rides the checkpoint

**Decision** (FR-017f–h, US4): a run resolves the **adopted version identifier** once at start
and passes it to every content read. The ask path gets this for free — one request, one
resolution. The dispatched path pins the version into the run's **checkpoint payload** (the
`payload: dict` the blob already carries), so a resumed run re-reads its ground *at the pinned
version* rather than re-resolving to current — the exact parallel of "re-authenticates, never
replays", and the reason R3 keeps superseded versions.

**The record names exactly one identity** (FR-017h): the endorsed version joins the ask/run
record next to `corpus_digest`, bounded vocabulary, one value.

**Alternative considered**: snapshotting content into the checkpoint itself (rejected — the
blob would carry megabytes of somebody's documents into the durability store, and the
version-addressed store already guarantees the same read).

## R5 — Detection is a health-checker probe; adoption is a console act; sync is platform code

**Measured**: the persistent MCP service already hosts the dependency **health checker** —
"reads dependency health, writes what its checker observed" — and the resume sweeper and 042's
scratch sweep, all for the same reason: they need a long-lived home.

**Decision**:

- **Detection** is a probe in that checker: for each endorsed source, compare the upstream tip
  (a remote-refs listing — no clone, no content transfer) against the adopted version's
  recorded tip, and write a **drift flag** the console reads. Noticing changes nothing
  (FR-017a); the flag is how the administrator is "notified" without anybody scheduling
  content changes.
- **Review** reads the difference on demand: when the administrator opens a pending change,
  the platform syncs the upstream into a **candidate version** (not adopted) and presents
  added/removed/altered documents against the adopted one (FR-017c). Reviewing against a
  candidate synced at review time is what makes "a source changes again while awaiting review"
  behave per the edge case — the review is against what is currently upstream.
- **Adoption** flips the governance record's `adopted_version` through the console's
  request-and-decide path. Runs in flight keep their pinned version (R4).

**Egress must be named** (R6): detection and sync reach customer sources from inside the
platform, which `corpus-sync` never did — it runs from `infra/bin` on an operator's machine.

## R6 — ADR-0070: endorsed-content sync is a new enumerated egress class

**Measured**: Principle II limits non-tool egress to enumerated classes — model inference,
identity, telemetry — and *"adding a class REQUIRES an ADR."* Syncing an endorsed source is
non-tool egress from a served process. There is no honest reading under an existing class.

**Decision**: **ADR-0070 — endorsed-content sync is an enumerated egress class** (Proposed,
this feature). Bounds stated in the record: only sources named in the endorsement record; only
during detection, review-sync, and endorsement-sync; **never during answering** (a row asserts
the answering path makes zero such requests — SC-003's mechanism); read-only; and the
credential story is explicit — public sources need none, and private-source credentials are
trust-store material referenced per sync, never entered through the console (044's FR-018b
posture).

**This is also where ADR-0030's tension resolves**: customer content is *consulted* material
handled by the **pinned** mechanism — sync-then-read, ADR-0021's labelled-snapshot shape —
because a customer's standard is ground for an attested answer, not a reference lookup.
ADR-0070 says so rather than leaving ADR-0030 describing a mechanism the tree does not use.

## R7 — The fourth console record, and the four places plus one

**Decision** (clarify Q3): `endorsed-sources` joins `CONSOLE_RECORDS`, the `authority_submit`
grant, `console_controlled_paths`, and `harness_authority_read` (exact path — 042's 020-lesson,
twice applied). The C6-shape completeness scan already asserts grant ↔ gate agreement; it gains
the new record, and the route's validator gains the record's parser (endorse/withdraw/adopt
shapes, `set_by`, CAS — all riding 044's `ConfigChange` unchanged).

**The sync itself is not a console write**: content flows into Postgres via platform code the
route triggers, not through the fabric. The fabric holds the governance facts (endorsed,
adopted version, by whom, when); Postgres holds the words.

## R8 — The answering path composes, the authoring path consults, one loader serves both

**Decision** (US5/US7): a single `load_endorsed(tenant, version)` reader returns an
`EndorsedCorpus`; the ask path wraps pin + endorsed into the combined resolution view; 042's
`compose_policy_evidence`-style citation checking on the authoring side receives the same
combined `resolves` callable. The disclosure travels as it did in 043/044: per-citation
provenance as data (R2), plus a summary in the answer's note field and in the proposal's
evidence section (FR-016). The age disclosure reuses `describe_ground`'s reasoning with the
endorsed version's sync time.

## R9 — What 045 does not build

- **No MCP-server sources** (spec assumption — the ROADMAP's own split).
- **No scheduler** — detection rides the existing checker; nothing new is operated.
- **No content vetting** — endorsement is attributable trust, not inspection; stated in the
  console the way 044 labels unconsumed records.
- **No multi-tenant enforcement beyond scoping** — `EndorsedCorpus` is keyed by tenant from
  day one (FR-019's hook), but cross-tenant *serving* isolation is ADR-0046's feature; a
  single-tenant enclave exercises the key without proving the wall.
- **No retention policy for superseded versions** — deferred with its reasoning (R3).

## R10 — Rows that must be able to lose

The safety rows, named early because each mirrors a prior feature's shape: content citable
without endorsement must fail a row (FR-021 — 044's C20 shape, the rigged-on construction);
the answering path making an outbound request must fail a row (SC-003 — asserted by
instrumentation, not absence of code); a run observing two content identities must fail a row
(SC-016/017 — asserted across a mid-run adoption and across a resume).
