# Conformance: answer usefulness (046)

Blocking properties this feature adds or preserves. Rows are hermetic unless marked *live*.

## Shape and grounding

| # | Property | How asserted |
| --- | --- | --- |
| S1 | An answered **guidance** response carries non-empty `primary_answer` and a `citations` array | Component/conformance on `ask_for` / API JSON |
| S2 | Every citation URL on an answered guidance response resolves (or carries endorsed provenance that resolves) | Product path with fixture corpus |
| S3 | A candidate with unresolvable citations does not ship as answered with those citations | Existing cite-resolve behaviour, regression |
| S4 | Portal renders `primary_answer` before supporting citations; legacy `claims[]` outcomes still render | Portal/component or snapshot |
| S5 | API and MCP agree on `disposition`, `primary_answer`, and `citations` for the same guidance ask | Parity row (extends ask parity) |

## Never-acts and safety

| # | Property | How asserted |
| --- | --- | --- |
| N1 | Ask path still has no tool registry and no authority grant | Existing never-acts row |
| N2 | Illustrative code in an answer creates no PR, `author_file`, or plan/apply side effect | Structural / no-dispatch assertion on ask |
| N3 | must-deny, must-decline, citation-accuracy, relevance gates remain green (or reauthored with recorded cause in this feature) | `make evals` / pack gates |

## Sufficiency

| # | Property | How asserted |
| --- | --- | --- |
| U1 | `answer_sufficiency` cases with empty `must_contain` are refused at load | Unit/loader row |
| U2 | A recorded true/cited/on-subject answer that omits a `must_contain` fact **fails** the suite | Hermetic scorer row (ADR-0047 — the suite can fail) |
| U3 | A recorded answer that includes every `must_contain` fact passes | Hermetic scorer row |
| U4 | Sufficiency does not retune the 043 relevance prompt | Diff/gate: relevance adapter instruction unchanged |

## Live (named runner)

| # | Property | Runner |
| --- | --- | --- |
| L1 | SC-002: fact present in primary answer ≥9/10 when material offered contains the fact | **Dan McTeer** — fails if credential/lane absent |
| L2 | SC-004: at least one illustrative-template ask returns code in `primary_answer` with resolvable citations | **Dan McTeer** |
| L3 | FR-010 measurement: for the retention-shaped question, record whether the fact-bearing section was offered | **Dan McTeer** — written into quickstart notes; if never offered, do not claim SC-002 closed without a retrieval follow-on |
| L4 | SC-001 walkthrough: three covered guidance questions; substance restatable without opening citations (3/3) | **Dan McTeer** — recorded in quickstart notes |

## Explicit non-goals (do not assert the opposite)

- Estate responses need not carry `primary_answer`.
- Thin locator answers need not decline when relevance passes (Q1-C).
- Relevance judge subject-vs-sufficiency instruction is not tightened.
