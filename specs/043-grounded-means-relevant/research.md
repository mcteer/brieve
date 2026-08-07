# Research: Grounded means relevant, not merely resolvable

Decisions under the two clarified answers (separate call; own cell rooted in a human-labelled
seed set). Each was checked against merged `main` rather than inferred.

## R1 — Where the gate sits, and how it cannot be silently absent

**Decision**: `answer_question` gains an optional `relevance` parameter (a `RelevanceJudge`).
When supplied, it runs **after** the keep/drop loop and **only when `kept` is non-empty**
(FR-018). When `None`, no judgement is performed — and the production caller
(`surfaces/api/ask.py`) **always supplies one**, which a row asserts against the caller rather
than against the function.

**Rationale**: The alternative — making the parameter required — would break every existing
caller including the recorded-fixture eval scorers, forcing edits to suites the spec promises
not to touch (SC-003, and the hermetic-gates assumption). The bypass risk of an optional
parameter is real and is answered the way this estate answers it: `verify-the-production-caller`
is a named lesson here, so the row drives `ask.py` and fails if it stops passing a judge. A
second row (FR-009) rigs the gate off and must fail.

**Alternatives considered**: gate inside the provider (rejected: the provider is the thing
being judged); gate at the surface only (rejected: the estate path and any future caller would
each reimplement it — Principle VII); a module-level default judge (rejected: a default model
choice is an ungoverned model choice).

## R2 — The cell, the binding, and what "own cell" means without widening the vocabulary

**Decision**: The judge occupies a matrix cell with the existing **`judge` role** — ADR-0039's
closed vocabulary is not widened — under its own cell identity (its own pack×model×judge key,
distinct from the eval judge's cell). Which cell the answering path uses is an
**operator-authored binding record**: `AskBinding` gains `relevance_cell` beside
`guidance_cell` and `estate_cell`, on 026's exact pattern. Unbound refuses `relevance_unbound`;
an unqualified or withdrawn cell declines with the resolution reason — both distinguishable
from a provider outage.

**Rationale**: 026 already decided this shape: *which* model is permitted is governance, *where*
one is reachable from is assembly, and "nobody decided" must surface before "nothing is wired".
FR-013's "own cell" is satisfied by cell identity plus its own qualification evidence — a new
*role* would amend an ADR to express something the cell key already expresses.

**Alternatives considered**: a new `relevance` role (rejected: widens a closed vocabulary by
interpretation — the shape v1.6.0's Sync Impact Report warns about); reusing the eval judge's
cell (rejected by clarification: qualified on refusal verdicts, and qualification does not
transfer); binding by deployment config (rejected by 026 explicitly).

## R3 — The verdict protocol

**Decision**: One call per ask. The judge receives the question and the surviving claims
(numbered), and returns a leading verdict line naming the relevant claim numbers —
`RELEVANT: 1,3` or `RELEVANT: none` — with nothing else required. Parsing is strict: a response
that does not start with the verdict token is **malformed**, and malformed **declines naming
the cause** (fail closed, FR-017's third leg). Kept = claims the judge named; none named →
decline "not covered".

**Rationale**: Per-claim verdicts are required by the spec's partial-keep edge case — an answer
with one relevant claim keeps it and discloses the rest. The leading-token protocol is 032's
recorded lesson (`harness-owns-model-vocabulary`): phrasing burdens live in the harness
protocol, never in per-model branches, and a verdict the platform must *search* for is one it
will eventually misread.

**Alternatives considered**: one boolean for the whole answer (rejected: fails the partial-keep
case and makes the judge cruder than the defect); per-claim separate calls (rejected: N× cost
for no independence gain — the claims share one question); asking for prose justification
(rejected for the gate itself: the *record* carries the verdict and the claim numbers; prose
would be a judgement nobody can parse. The seed-set qualification is where discrimination is
proven).

## R4 — The seed set, and the case that can fail

**Decision**: `evals/relevance-seed/seed.toml`, loaded by a new `core/evals/relevance_seed.py`.
Each case: `id`, `question`, `claims` (statements with citations that RESOLVE against the real
pin), `verdict` per claim (`relevant`/`irrelevant`), and **`author`, required and non-empty**
(038's corpus precedent — generated labels measure the generator against itself; ADR-0052's
existing `SeedCase` has no author field, and this loader is separate rather than a widening of
that one so the existing judge chain is untouched). Floor: ≥10 cases; at least **3
supported-but-irrelevant** cases (FR-015's shape — resolving citations, true statements, wrong
subject, of which the motivating retention case is the first); at least 3 fully-relevant; at
least one partial (mixed verdicts in one case). Qualification: the candidate judge must reach
the ADR-0052 floor (≥90%) **and** must fail... precisely: must *correctly reject* every
supported-but-irrelevant case — a judge that only passes the easy majority is refused.

**Rationale**: FR-014/FR-015. The supported-but-irrelevant cases are the entire point: a seed
set without them qualifies a judge on verdicts the defect never presents.

**Alternatives considered**: widening `judge.py`'s `SeedCase` (rejected: it would touch the
existing judge chain's loader and floor to serve a different verdict vocabulary); generating
seeds from the corpus (rejected by FR-014 explicitly).

## R5 — The decline vocabulary and the record

**Decision**: `Answer.declined_reason` gains a third string — *"the corpus does not cover what
was asked"* — used when the judge names no claim. `Answer` gains `irrelevant: tuple[str, ...]`
(statements dropped by the gate, disclosed like `dropped`) and a `relevance` note naming the
verdict and that a model made it. On the surface, `ask.py` writes a **`MODEL_GATE`** audit
event — the type exists and has never had a production writer; this is its first — with payload
`{gate: "relevance", verdict, kept, dropped}` and the cell identity, before `ASK_ANSWERED`/the
decline record, so a reader meets the gate before the outcome it produced (031's
fallback-before-issued ordering precedent).

**Rationale**: FR-002/FR-006/FR-016 and SC-006/SC-007. Principle IX requires model gates be
distinguishable from human approvals in the trail; `MODEL_GATE` is the vocabulary built for
exactly this and never yet used in production.

**Alternatives considered**: overloading `dropped` (rejected: FR-002 requires the two grounds
be distinguishable, and `dropped` already means "did not resolve"); a new audit event type
(rejected: schema is sealed core and the existing type is this case by name).

## R6 — The fixture judge, and how the blocking lanes stay honest

**Decision**: A fixture relevance judge for hermetic lanes: deterministic, driven by the case's
own expectations (the recorded suites' cases gain nothing — the fixture judge affirms all
claims for cases that expect `answered`, which preserves SC-003 by construction, and the rows
that exercise the gate's *teeth* construct their own claims). A fixture cell
(`qualified_by="fixture"`, its own key) joins the dev estate beside every other fixture cell,
and the binding record points at it — so `make dev-up` yields a working surface with the gate
present, and the FR-009 rig-off row and the malformed/unavailable rows drive the seams
directly.

**Rationale**: The fork-safe lane cannot call a vendor; a gate absent under test violates
FR-017's spirit and would leave the production wiring unexercised — the 038 lesson. A fixture
that affirms-by-default is safe *only because* dedicated rows drive the refusing branches, and
the contract says so explicitly rather than letting the default read as coverage.

**Alternatives considered**: skipping the gate in hermetic lanes (rejected: silently absent);
a keyword-matching fixture (rejected: it would be a second relevance implementation whose
disagreements with the real one mean nothing).

## R7 — Scope: the guidance route only

**Decision**: The gate applies to **guidance** answers. Estate answers are out of scope: their
claims cite the asker's own run records, already bounded by role scope and the 029 window — an
estate answer's relevance failure mode is routing, which 029 already owns.

**Rationale**: 0g's case is a guidance case; the defect mechanism (corpus breadth) does not
exist on the estate path, whose "corpus" is the tenant's own trail. Widening the gate there
would spend a model call per estate ask against a defect nobody has observed.

**Alternatives considered**: both routes (rejected as above — and recorded as the thing to
revisit if an estate analogue is ever observed).

## R8 — The live legs

**Decision**: Smoke gains a relevance leg — the retention case through the real path with the
live judge, response printed (the one-call-before-180 rule). Qualification runs the seed set
against the candidate judge cell and prints per-case verdicts plus the two counts (majority
floor; supported-but-irrelevant all-correct). Sampling: the smoke leg is one call by design;
the **qualification** takes majority-of-three per seed case, inheriting the answering lane's
recorded lesson rather than re-learning it (and unlike 041's authoring lane, this one is
deciding a cell, which is exactly where single samples produced three different pass/fail
sets).

**Rationale**: SC-001/SC-002/SC-008; the estate's standing rules on debugging with the cheap
call first and on majority sampling where cells are decided.

**Alternatives considered**: single-sample qualification (rejected: the recorded lesson);
majority-of-three in smoke (rejected: smoke diagnoses the harness, and three samples of a
broken protocol are three copies of the same defect).

## Resolved unknowns from Technical Context

None remain. The seed set's authorship is the one human dependency: the plan's floor needs
≥10 authored cases, and they are written during implementation and reviewed like code — with
the motivating retention case as the first supported-but-irrelevant seed.
