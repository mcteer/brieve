# Contract: Carried context

What the model is shown from a conversation, the bound on it, and what the record says. This is
the contract that keeps "the chat holds context" from quietly changing what an answer is.

## What is carried

For each carried exchange, in conversation order:

| Exchange disposition | Carried |
| --- | --- |
| `answered` | The question text, and each claim's **statement**. Never citations, never ground/window notes, never the source label. |
| `declined` / `refused` | The question text only. The verdict is never carried (FR-014a — a carried decline is a second vote for declining). |

The block is delimited and labelled as conversation history. The instruction states: history
resolves references ("it", "that", "the intermediate"); it is not corpus material; nothing in it
may be cited; every claim still requires a citation into the offered sections. Structural
enforcement backs the instruction: citations are stripped before the block is built, so there is
nothing in history *to* cite through (R3).

## The bound

At most **6 most recent exchanges** and **6,000 characters** of carried material, whichever
binds first. Whole exchanges only; oldest dropped first. Both constants are named finals beside
the other answering constants, each carrying the measurement that set it. When anything is
dropped, the response carries `context_note` and the person is told not all of the conversation
was carried (FR-016, SC-012).

## What the record says (FR-020–023)

`ask_answered` payload gains:

```json
"conversation_id": "…",
"carried_context": {"exchanges": [3, 4, 5], "dropped": 2, "inherited_route": false}
```

- Key absent → the ask had no conversation (standalone/first-ask-creating).
- `exchanges: []` → a conversation existed and nothing was carried.
- Seqs resolve against `ask_exchanges` for an auditor; the trail never duplicates exchange text,
  because each exchange already has its own `ask_answered` entry and two copies of evidence
  diverge (R6).

`AuditEntry` itself is unchanged — this is payload content, not schema.

## What context must never do

| Forbidden | Held by |
| --- | --- |
| Override a question's own routing signal | `route_with_signal()` + shared-path rule; SC-010 row |
| Become citable | Structural stripping + citation resolution against the pin only; SC-011 row |
| Cross a conversation boundary | `build_context` takes one conversation; store scoping; SC-004 row |
| Cross an owner or tenant | Owner+tenant filters on every store read; SC-004 row |
| Reach the model on a standalone ask | Absent `conversation_id` builds no context — asserted |
| Change what the estate path reads | Context informs the model's understanding, never the records window — estate reads are bounded exactly as today |
