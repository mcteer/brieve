<!-- SPDX-License-Identifier: Apache-2.0 -->
# Quickstart: 022 — proving a read leaves a record

How to validate this feature end to end. **The last scenario is the one that matters**, because it
is the one whose absence let this defect ship: the others can pass against a test double, and the
defect was found by connecting a real editor to a running service.

---

## Prerequisites

```bash
make dev-up                 # Postgres, Nomad, Vault, dev IdP
docker run --rm --privileged alpine hwclock -s   # VM clock drift breaks attestation
```

Start the dev IdP with a token lifetime you can actually paste (`DEV_IDP_TOKEN_MINUTES=480`) if
you intend to drive the surface from an editor rather than curl.

---

## 1. The hermetic rows — nothing running required

```bash
make check
```

**Expect**: the new component rows pass —

- a covered read appends to `record-access:{tenant}`, and a read returning nothing appends too
- a refused read appends a refusal, keeping the distinction the caller cannot see
- **the entry comes back through the governed evidence read**, and is refused to another tenant
- **the seven operations answer exactly as they did before** — same records, same refusals, same status
- a planted credential-shaped value reaches no entry
- every covered operation refuses when the sink is made to fail, listings included
- reading a run leaves that run's own chain byte-identical

**Expect also**: `tests/unit/test_audit_chain.py` passes with the pinned digest **unchanged**. If
that literal moved, stop. The encoding changed and every entry ever written is at risk; nothing
else in this feature matters until that is understood.

---

## 2. The claim matches behavior

```bash
uv run pytest tests/component -k "claim or disposition" -q
```

**Expect**: the surfaces' governance sentence is derived from the operation catalogue, and a
disposition changed without the sentence changing is impossible rather than merely tested.

**Try to break it**: change one operation's disposition from `records` to `no_record` without
touching anything else. The derived sentence must change with it, and a row must fail because the
operation no longer records what it declares.

---

## 3. Both surfaces agree, including when the trail is down

```bash
make conformance
```

**Expect**: `EXIT=0`, with the parity rows covering all seven operations on both transports — and
covering the **failure** path, not only the happy one. Research F7 found the existing evidence
path has no parity there: it raises an HTTPException that the MCP transport does not catch. If the
six new sites are correct and the adjacent fix landed, both surfaces now return the same verdict
when a record cannot be written.

**This needs the enclave**, which is `workflow_dispatch` only. It will not run on your PR. See the
conformance contract — it is owed, by name.

---

## 4. The row that proves 021 still holds

```bash
uv run pytest tests/conformance/reports -q
```

**Expect**: after reading a run, that run's chain is byte-identical, and a report compiled for it
carries no claim about who read it.

**Why this exists**: the first draft of this spec required a read to join the run's own walk. That
would have put "who read this run" inside the report of that run — including reads of the report —
growing every time anyone looked. The row is the guard against that reasoning coming back.

---

## 5. The one that would have caught the original defect

**Do this against a served surface. Not a test double. That is the whole point.**

```bash
# 1. Serve the surfaces
make dev-up

# 2. Mint a token and connect — an editor, or curl
DEV_IDP_ISSUER=http://127.0.0.1:8090 PYTHONPATH=. \
  uv run --extra surfaces --extra adapters python -c "
from tests.conformance.mcp_served import surfaces
print(surfaces.caller_token(subject='caller-1', tenant='tenant-local',
                            permissions=['platform:operator']))" > /tmp/brieve-token

# 3. Start a run, let it finish, then read its result through the surface

# 4. Ask the trail who read it — THROUGH THE GOVERNED PATH, not through Postgres.
#    Call read_evidence on the same surface, with the reader stream's correlation id:
#      correlation_id = "record-access:tenant-local"
```

**Expect**: a `record_read` entry naming `caller-1`, the operation, and the run's correlation id.

**Use the governed read, not `psql`.** SC-002 says "discoverable through the governed read path",
and a direct SQL query proves the row exists while proving nothing about the criterion. An earlier
draft of this file used `psql` here — and because it did, nothing in the feature demonstrated that
the record-access stream is reachable through the path FR-005b requires. Analysis caught it; T023a
is the row that now covers it. Reach for `psql` only when the governed read has already failed and
you are working out why.

**Before this feature, that query returns nothing** — which is exactly what it returned on
2026-08-01, with the whole suite green and both surfaces telling every connecting client that every
operation is recorded in a tamper-evident trail.

**Then read the run's report and check the run's own chain is unchanged**, so the record of your
read did not become part of what the report describes.

---

## Definition of done

- `make check` green, pinned digest unmoved
- `make conformance` `EXIT=0` on a live enclave — **owed, named in the contract**
- Scenario 5 performed against a served surface — **owed, named in the contract**
- ADR-0035 amended in the same change (Principle X)
- Security review requested on the PR for the four additive members (Principle V)

The last two are not test rows and cannot go green on their own. They are recorded in the
conformance contract by name so that merging without them is visibly a gate regression.
