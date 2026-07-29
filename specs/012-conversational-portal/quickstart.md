# Quickstart: validating the portal

**Feature**: `specs/012-conversational-portal` | **Date**: 2026-07-29

How to prove the feature end to end. Commands marked **(runs today)** are Phase 0 probes;
re-running them checks the ground has not moved.

## 1 — The findings are real *(runs today)*

```bash
# F1: a dispatched run receives no input of any kind
grep -c "input\|message" src/surfaces/dispatch/types.py     # -> 0 relevant
grep "RUN_" src/surfaces/dispatch/entrypoint.py             # identity/scope/resume only

# F2: nothing serves the API
ls infra/jobs/ | grep -c api                                # -> 0
```

## 2 — Parity is the loop *(after each snapshot growth)*

```bash
uv run --extra adapters --extra surfaces pytest tests/conformance/mcp/test_surface_parity.py -q
```

**Expect**: red after the snapshot grows past the implemented set; green at fifteen on
both. Five reds and five greens, one per operation, in commit order.

## 3 — Threads, hermetically *(after core lands)*

```bash
uv run --extra adapters --extra surfaces pytest tests/component -k "thread or turn" -q
```

Covers: evidence-first ordering (including the decline branch), verbatim context and its
bound, the tenant collapse, deletion leaving the trail whole, rate refusal, seq under
concurrent sends.

## 4 — The portal, in a browser *(after the client lands)*

```bash
make dev-up && make dev-status
make portal-up                 # dev IdP + API + portal, deliberately separate from bring-up
nomad job status api && nomad job status portal
open http://127.0.0.1:8082/    # log in via the dev IdP, PKCE flow
```

**Why `portal-up` is its own target**: bring-up stands up the platform, and every gate
reaches Vault, Nomad, Postgres, the MCP service, and agent-run. These three serve a
browser — and one of them is an identity provider that authenticates nobody, which should
be something a person chooses to run.

Walk US1→US4: see definitions (startable and not, flagged); start a run in a thread;
watch it move without refreshing; send a follow-up that references the first result;
restart the portal allocation and find the thread intact; stop a run mid-flight; delete a
thread and read the exchange back from evidence.

## 5 — Containment *(after the portal lands)*

```bash
uv run --extra adapters --extra surfaces pytest tests/conformance/portal -q
```

**Expect**: every portal request maps onto catalogued operations; one egress module; no
credential in the portal; nothing in browser storage but the cookie.

## 6 — Accessibility *(after the client lands)*

```bash
make a11y
```

**Expect**: green on the automated WCAG 2.2 AA ruleset over every page state — and the
run's output names the criteria it did NOT assert, pointing at the manual checklist in
[contracts/conformance-portal.md](contracts/conformance-portal.md).

## What a passing run does NOT prove

- Anything about answering — estate-state and guidance are the follow-on feature's, after
  capability packs.
- Full WCAG 2.2 AA conformance — the automated gate asserts its subset; the manual
  checklist (named runner: Dan) covers the rest, per FR-020a-i.
- Multi-tenant thread isolation beyond the single-registry reality 011 recorded (FR-013a
  inherited).
- Production TLS posture between portal and API — dev is loopback inside the enclave;
  the jobspec comments carry the deployment note.
