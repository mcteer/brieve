# Data Model: An answer is useful

## Entities

### PrimaryAnswer (wire, guidance answered)

| Field | Type | Rules |
| --- | --- | --- |
| `primary_answer` | string | Required when `disposition == "answered"` and `source` is guidance (or endorsed guidance). Non-empty after strip. May include fenced illustrative code. |
| `citations` | list of SupportingCitation | Required when answered; may be empty only if the platform would have declined — an answered guidance response with zero citations is invalid (grounding). Deduped by URL. |
| `disposition` | `"answered"` \| `"declined"` \| refused at HTTP layer | Unchanged vocabulary. |
| `source` | string | `"guidance"` (estate unchanged / out of scope). |
| `corpus_digest`, `ground_note`, `relevance_note`, `grounding_note`, … | as today | Unchanged optional metadata. |

Legacy replay: outcomes that lack `primary_answer` but carry `claims[]` remain renderable.

### SupportingCitation (wire)

| Field | Type | Rules |
| --- | --- | --- |
| `url` | string | Absolute URL from `corpus.url_for(path, anchor)` (or endorsed equivalent). |
| `provenance` | string | `validated-design` \| `customer-endorsed` (045). |

### Claim (internal governance seam — unchanged type)

| Field | Type | Rules |
| --- | --- | --- |
| `statement` | string | For 046 guidance live path: the primary answer text (one claim). |
| `citations` | tuple of `Citation(path, anchor)` | Every citation must `corpus.resolves` or the claim is dropped. |

Relevance still receives `[claim.statement, …]` (typically length 1).

### ProviderCandidate (adapter output)

| Field | Type | Rules |
| --- | --- | --- |
| `answer` | string | Primary prose/code. |
| `citations` | list of `{path, anchor}` | Verbatim from offered section headers only. |

Mapped to a single `Claim` before `answer_question`. Empty answer or empty citation list → no keep → decline (existing rules).

### SufficiencyCase (eval)

| Field | Type | Rules |
| --- | --- | --- |
| `id` | string | Unique. |
| `suite` | `"answer_sufficiency"` | Exact. |
| `prompt` | string | Question. |
| `recorded` | string | Candidate model output (JSON object shape) for hermetic product-path scoring. |
| `must_contain` | list of string | **Non-empty.** Every entry must appear in the resulting `primary_answer` (case-insensitive, whitespace-normalised) for the case to pass. Cases encode facts that were available to the path; they do not require a locator-disclosure form (Q1-C). |

A case with empty `must_contain` is refused at load (same doctrine as empty `events` on fidelity — a suite that cannot fail is a governance hole).

### AskAnswered (audit — unchanged)

No answer text. Continues to carry subject, digest, disposition, cell, relevance_gate, model_authority, etc. Sufficiency does not add audit fields.

## Validation rules

1. Answered guidance without `primary_answer` → surface bug (tests must catch).
2. Answered guidance with citations that did not resolve → impossible if gate held; conformance asserts absence.
3. Illustrative code in `primary_answer` does not create tools, grants, or side effects.
4. Estate payloads MUST NOT be required to carry `primary_answer` in this feature.

## State transitions

```text
provider candidate
  → Claim(statement=answer, citations=path/anchor)
  → cite-resolve keep/drop
  → relevance keep/drop (043)
  → wire { primary_answer, citations[] } | declined
```
