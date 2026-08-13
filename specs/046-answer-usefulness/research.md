# Research: An answer is useful — primary response, supporting citations

Decisions under clarifications Q1-C (thin answers allowed) and Q2-B (guidance/endorsed only;
estate unchanged). Checked against the answering path on this branch's base rather than
inferred.

## R1 — Wire shape: primary answer first, citations as support

**Decision**: Guidance answered responses gain `primary_answer: str` and a top-level
`citations: [{url, provenance}]` list. The portal renders the primary body first, then
supporting sources. Estate responses keep today's `claims[].references` shape.

**Rationale**: Spec US1/FR-001/FR-003. Today's `<ol class="claims">` over one-sentence
statements *is* the citation-led UX. A top-level primary body matches what a person asked for
without dropping resolvable sources.

**Alternatives considered**: Keep `claims[]` as the only wire shape and restyle the portal
(rejected: still trains the model toward fragmented sentences); put code only in a separate
`code` field (rejected: over-structures content the model should place in the answer).

## R2 — Governance seam stays claim-shaped; composition at the surface

**Decision**: `answer_question` continues to gate on `Claim(statement, citations)` —
citation resolution, then relevance on `Sequence[str]` of statements (043 unchanged). The
live provider is instructed to return **one** primary answer object whose text becomes the
single claim statement and whose citation list is the support set. `ask_for` composes the
wire fields from the kept claim: `primary_answer` = that claim's statement;
`citations` = deduped resolved URLs with provenance.

**Rationale**: `RelevanceJudge.assess(question, claims: Sequence[str])` is built for numbered
statements and must not be retuned (FR-009). A length-1 sequence is valid. Rewriting the gate
around free-form prose would churn sealed relevance behaviour for a presentation change.
Never-acts is preserved: the provider still holds corpus + client only.

**Alternatives considered**: Pass only `primary_answer` into relevance and drop claims
(rejected as the sole internal shape if it deletes per-citation resolution); judge after
surface composition (rejected: gate must sit in core on the product path); multi-claim
compose with separate "write a paragraph" step (rejected: two model jobs, more drift).

## R3 — Provider instruction: answer, then cite — allow illustrative code

**Decision**: Replace the guidance `_INSTRUCTION` requirement of a JSON **array of one-sentence
statements** with a JSON **object**:

```json
{
  "answer": "primary prose; fenced code when the asker wants an example the sections support",
  "citations": [{"path": "...", "anchor": "..."}]
}
```

Rules retained verbatim in spirit: cite only offered section headers; `[]`/empty citations
with no answer when unsupported; never invent paths/anchors; never claim to have acted.
Illustrative code is allowed in `answer` when the question asks for an example/template and
the sections support it.

**Rationale**: FR-004/FR-005 and the 2026-08-13 walkthrough. The old "one factual sentence"
contract is what produced citation-led fragments.

**Alternatives considered**: Keep the array and concatenate in the surface (rejected: model
still optimises for short claims); allow uncited code "as illustration" (rejected: FR-005 /
fail-closed).

## R4 — Backward compatibility for stored conversations

**Decision**: Portal (and any conversation replay) accepts **both** shapes: new
`primary_answer` + `citations`, and legacy `claims[]`. New answers write the new shape (and
MAY still include `claims` for one release if parity tests need it — research preference:
**omit `claims` on new guidance answers** once scorers and parity are updated, to avoid two
sources of truth).

**Rationale**: 045 already taught dual-shape citation objects vs bare URL strings for replay.
Reopening an old thread must show what the person saw.

**Alternatives considered**: Migrate stored outcomes (rejected: mutates evidence of past
answers); break old threads (rejected).

## R5 — Sufficiency suite shape (fifth answering concern, additive)

**Decision**: New suite `answer_sufficiency`, **not** forced into `expected: str`. Case fields:

| Field | Role |
| --- | --- |
| `id`, `suite`, `prompt` | as today |
| `recorded` | model candidate JSON (product path via `AnsweringScorer` / `RecordedProvider`) |
| `must_contain` | non-empty list of substrings the **primary answer** must include |

Scoring: run the product path; on `answered`, require every `must_contain` entry to appear in
`primary_answer` (case-insensitive, whitespace-normalised). A true/cited/on-subject locator
that omits the fact **fails**. On `declined`, fail the case unless the case explicitly marks
decline as acceptable (default: sufficiency cases expect an answer). Hermetic: fixture
provider + recorded candidates. Live SC-002 remains a named-runner sampling bar, not the
merge gate.

Membership: add to pack `SUITES` with a dedicated scorer branch (precedent: `report_fidelity`
/`MEASURED_SUITES` and `estate_state` — verb-shaped `expected` is the wrong tool). Do **not**
put sufficiency into `ANSWERING_SUITES`'s `cited`/`decline` judge.

**Rationale**: FR-006, SC-003, ADR-0047; ROADMAP warned that `expected: str` loses the signal
(`report_fidelity` lesson).

**Alternatives considered**: Tighten 043 relevance prompt (rejected by ROADMAP / FR-009);
second sufficiency model gate (rejected for v1: cost + 043's measured over-refusal risk;
revisit only if the suite cannot land).

## R6 — Retrieval measurement (FR-010), not a new retriever by default

**Decision**: During implementation research/quickstart, measure whether the sections offered
for the ROADMAP-shaped retention question include the section that holds the fact versus only
a preamble. Record the result in this feature's notes or a short appendix to quickstart.
**Do not** ship embeddings or a new index in 046 unless that measurement shows the fact
section is never offered — in which case stop and specify a retrieval follow-on rather than
claiming SC-002 closed.

**Rationale**: Spec FR-010 and ROADMAP candidate "retrieval problem." Presentation +
sufficiency suite close the shape and the fail-able gate; they cannot invent a section the
retriever never showed.

**Alternatives considered**: Mandate a retriever rewrite in this feature (rejected: scope
explosion without measurement).

## R7 — Parity, audit, never-acts

**Decision**: API and MCP continue to share `ask_for`; parity asserts on
`disposition` / `primary_answer` / `citations` for guidance. `ask_answered` remains
content-free (never question, never answer text). FR-008 (as remediated) is satisfied by
existing cell / corpus_digest / disposition / relevance_gate fields — **not** by writing
per-citation source lists into the audit payload. No new tool registry or authority grant on
the ask path.

**Rationale**: ADR-0033, ADR-0039, existing `record_ask` doctrine.

**Alternatives considered**: Store primary_answer in audit (rejected: contradicts
ask_answered's sealed purpose).

## R8 — Sealed-core touch

**Decision**: Additive/behavioural edits in `adapters/anthropic_answering.py` (instruction +
parse), `surfaces/api/ask.py` (wire composition), portal template, `core/evals` suite/scorer
wiring, pack TOML cases. Prefer **not** changing `Answer` fields if composition can live in
`ask_for`; if `Answer` needs `primary_answer` for a single seam, keep it additive. Relevance
adapter **untouched**. Security review owed only if sealed adapter behaviour widens what can
ship without citations — the design forbids that.

**Rationale**: Principle V — smallest sealed touch; governance order unchanged.
