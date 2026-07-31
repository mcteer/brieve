# Quickstart: Task-scoped authority manufacture

**Feature**: `specs/016-task-scoped-authority` | **Date**: 2026-07-31

Six sections. Section 0 runs **today, before implementation**, and is the one that decides
whether the rest of the plan is buildable as written.

## Prerequisites

```bash
make dev-up            # brings up the enclave; after this feature, also activates the flag
```

Vault v2.0.3+ent. Enterprise is required — `oauth-resource-server` and the agent registry are
Enterprise features.

---

## 0 — Settle entity resolution *(runs today; blocks everything else)*

Research F5 left one thing open: how a grant's `sub` binds to a Vault Identity entity. With a
valid signature, a well-formed schema, and RAR details present, Vault still refuses:

```text
2 errors occurred:
  * no alias found
  * error looking up entity
```

**Expect**: an established, reproducible binding between a grant's subject and a registered
agent's entity. In the order worth trying:

```bash
# 1. HashiCorp's own end-to-end example for this exact path
git clone https://github.com/hashicorp-education/learn-vault-agentic-iam

# 2. What the alias endpoint will actually accept
vault path-help identity/entity-alias

# 3. The resolution attempt, with more structure than the server log's summary
vault audit enable file file_path=/tmp/vault-audit.log
#    ...present a grant, then read the entry...
vault audit disable file
```

**Until this returns an answer, nothing below can be demonstrated** — and that is why it is
section 0 rather than an appendix.

---

## 1 — The gap is real *(runs today)*

```bash
# What a run's token carries now: the definition's whole ceiling, for the whole run.
vault read auth/nomad/role/agent-run | grep token_policies
vault policy read agent-ceiling-planner
```

**Expect**: `token_policies` naming policies that grant the definition's full path set, with
nothing anywhere expressing what *this run's task* needs. That absence is the `task scope`
term in Principle IV's intersection.

---

## 2 — A grant reaches its task and nothing more *(after implementation)*

```bash
uv run --extra adapters --extra surfaces --extra portal pytest \
  tests/conformance/authority -m host_enclave -q
```

**Expect**: a run whose tools entail one path reads it, and is refused a second path the
definition's ceiling permits. See
[contracts/conformance-task-authority.md](contracts/conformance-task-authority.md) for the
full row list.

---

## 3 — The refusal is the trust store's, not ours

Present the grant to Vault directly, with the platform's own hook pipeline entirely out of
the picture.

**Expect**: the out-of-task path is still refused. This is the row the feature exists for —
every other refusal in this system is one our own code produced, and this is the one that
holds when our code is wrong.

**Note when reading failures**: a RAR rejection returns a bare `403 permission denied`. The
reason lives in the Vault server's log (`docker logs <vault>`), never in the response. Check
there first; the response will not tell you whether the problem was the signature, the
schema, the entity, or the scope.

---

## 4 — A resume keeps the scope, and the record is not a credential

```bash
# Disrupt a run mid-task, let it resume, compare grants.
# Then present the recorded grant's bytes directly to Vault.
```

**Expect**: the resumed run's scope is identical to the launch grant's — no person present,
no widening. And the record itself obtains nothing when presented as a token: it is a
description of authority, not authority.

---

## 5 — The posture says which arrangement is in force

```bash
# Configure federated, platform-issued, and unconfigured in turn; read the posture.
```

**Expect**: each reports as itself with a reason. The unconfigured case says so plainly
rather than defaulting to a value that reads as protected — an operator holding a false
assurance is the failure this platform legislates against elsewhere.

---

## 6 — Nothing else moved

```bash
make check && make conformance
```

**Expect**: tool authority decisions unchanged (this feature narrows resource access only),
the standing-credential count unchanged, and every existing lane green.

---

## What a passing run does NOT prove

- **That the narrowing is tight.** It is as tight as the tools' path declarations and no
  tighter. A broadly-declaring tool yields a broad grant.
- **That a compromised allocation is contained.** The grant bounds what its token reaches, not
  what a process might obtain by other means.
- **That a customer's IdP can do the federated tier.** The dev enclave's issuer stands in for
  one. Whether Okta, Ping, or IBM Verify will mint a custom RAR type was not established, and
  ADR-0056 says so.
