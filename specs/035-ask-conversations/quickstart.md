# Quickstart: Ask becomes a conversation

Validation guide — how to prove the feature works end to end. Contracts in
[contracts/](contracts/), shapes in [data-model.md](data-model.md).

## Prerequisites

```sh
make dev-up                      # enclave, Vault, Postgres, Nomad
DEV_IDP=1 bash infra/bin/portal-up   # both surfaces, development identity
```

The model credential must be seeded (`model-credentials/anthropic`) — re-seed after any
dev-estate `terraform apply`.

## Fast checks (no model)

```sh
make check                       # component rows: store, context builder, inheritance, record keys
make conformance-hermetic        # parity rows, 404 identity, delete-vs-trail, routing rows
make a11y                        # every transcript state, both themes, 320px, sticky composer
```

Expected: all green. The containment session performs every new operation and still reports
zero uncatalogued requests.

## The conversation, through the served portal

1. Open `https://127.0.0.1:8082/ask`, sign in.
2. Ask *"How do I run a Vault cluster in AWS?"* → answer appears as an exchange; page did not
   navigate; conversation appears in the rail with a derived title.
3. Ask *"what about multi-region?"* → answer addresses multi-region **Vault clustering** with
   resolving citations (SC-001/002). Transcript now shows both exchanges.
4. Reload → conversation listed; open it → both exchanges in order (SC-003).
5. Ask *"which runs failed last night?"* inside the same conversation → routes to **estate**
   (own signal wins; SC-010) — check `Consulted: estate` on the exchange.
6. Delete the conversation via its confirmation page → gone from the list.

## The record (SC-005/006)

```sh
docker exec <postgres-container> psql -U brieve -d brieve -c \
  "SELECT payload->>'conversation_id', payload->'carried_context'
   FROM audit_entries WHERE event_type='ask_answered'
   ORDER BY timestamp DESC LIMIT 5;"
```

Expected: the follow-up's row carries the conversation id and `{"exchanges":[1],...}`; the
first ask carries `"exchanges": []` or no key per contract. After deleting the conversation,
re-run: rows unchanged.

## Transport parity (SC-013)

Drive the MCP surface (`infra/bin/mcp-surface-up`, then the conformance client): `ask` with and
without `conversation_id`, `ask_conversations`, `ask_conversation`, `delete_ask_conversation` —
same outcomes, same 404 wording for a foreign id, as the API.

## The live check (SC-002 — before promotion, not in CI)

Ten realistic signal-less follow-ups across the corpus families, each after a real first
question, through `LiveAnswerProvider` at the provider seam (cheap) and then two through the
served portal (honest). Pass: ≥ 9/10 answered about the subject under discussion. Judged on
answers, not rankings — the A/B-at-the-provider-seam lesson.

## What "done" looks like

- Every fast-lane and a11y row green in CI; live check ≥ 9/10, recorded in the PR.
- The served portal walk-through above completes with zero page navigations after sign-in.
- `operations.snapshot.json` carries the three new operations; the containment session covers
  them; both transports answer identically.
- The trail is byte-identical across a conversation delete.
