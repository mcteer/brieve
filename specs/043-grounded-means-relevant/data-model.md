# Data Model: Grounded means relevant, not merely resolvable

Most of the answering shapes exist and are widened additively. New entities are the judge
protocol, its verdict, and the seed case.

## New entities

### RelevanceJudge (`core/answering/relevance.py`)

The protocol both judges implement — the live adapter and the hermetic fixture.

| Member | Notes |
| --- | --- |
| `assess(question, claims) -> RelevanceVerdict` | One call per ask; only invoked when `kept` is non-empty (FR-018) |

**Failure contract**: unreachable, unqualified, or malformed output all surface as a typed
refusal the caller turns into a decline naming the cause — never an exception that escapes as
a provider fault, because "the judge could not assess" and "the model could not answer" send a
reader to different places (FR-017).

### RelevanceVerdict

| Field | Type | Notes |
| --- | --- | --- |
| `relevant` | `frozenset[int]` | Indices of claims the judge affirmed. Empty is a real verdict: decline "not covered" |
| `model` | `str` | The cell's model identity, for the `MODEL_GATE` record |
| `raw_leading_token` | `str` | What was parsed, kept for the record — the verdict word is the protocol (032's rule) |

### RelevanceSeed (`core/evals/relevance_seed.py`)

| Field | Type | Notes |
| --- | --- | --- |
| `id` / `question` | `str` | |
| `claims` | `tuple[SeedClaim, ...]` | Statement + citation that **resolves against the real pin** — a seed citing nothing real would qualify the judge on a world the path never produces |
| `verdicts` | per-claim `relevant`/`irrelevant` | Human-chosen, closed vocabulary, refused otherwise |
| `author` | `str`, required non-empty | 038's corpus precedent; generated labels measure the generator |

**Floor (enforced at load, fails never warns)**: ≥10 cases; ≥3 supported-but-irrelevant; ≥3
fully-relevant; ≥1 mixed. Separate loader from `judge.py`'s `SeedCase` so the existing judge
chain's floor and vocabulary are untouched.

## Widened entities

### `Answer` (`core/answering/answer.py`)

- `declined_reason` gains a third value: *"the corpus does not cover what was asked"* (FR-002).
- New `irrelevant: tuple[str, ...]` — statements dropped by the gate, disclosed distinctly from
  `dropped` (which keeps meaning "citation did not resolve").
- New `relevance_note: str` — the disclosure that a model judged relevance, carried on answers
  and declines alike (FR-007: a model judgement, never a platform fact).

### `AskBinding` (`core/authority/ask_binding.py`)

- New `relevance_cell: str = ""` beside `guidance_cell`/`estate_cell`. Absent → the surface
  declines `relevance_unbound` (026: "nobody decided" precedes "nothing is wired").

### `answer_question`

- New optional `relevance: RelevanceJudge | None = None`. `None` performs no judgement; the
  production caller always supplies one, asserted by a row against `ask.py` itself
  (`verify-the-production-caller`).

### Audit (no schema change)

- **`MODEL_GATE` gains its first production writer.** Payload: `{gate: "relevance", verdict,
  kept_count, irrelevant_count, model, cell}` — written before the ask outcome record, so a
  reader meets the gate before what it produced. Statements do not enter the payload; the
  answer record already carries them once.

### Trust fabric (`infra/modules/trust-fabric/`)

- The ask-binding record gains `relevance_cell`; the dev estate gains a fixture judge cell
  (its own key, `qualified_by="fixture"`) so `make dev-up` has the gate present and bound.

## State transitions

Ask flow (guidance route only — R7): candidates → keep/drop by citation resolution →
(`kept` empty → decline, unchanged) → **relevance gate** → all affirmed → answered · some →
answered with `irrelevant` disclosed · none → declined "not covered" · judge
unavailable/unqualified/malformed → declined naming that cause.
