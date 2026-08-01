<!-- SPDX-License-Identifier: Apache-2.0 -->
# Quickstart: attach a client to the served MCP surface

How to prove this feature works end to end, and how to watch it refuse something.

**Nothing here is runnable yet** — the feature is planned, not implemented. This is the
validation guide the implementation must make true, and the acceptance test for FR-015: if
someone cannot connect by following it without reading source, FR-015 is not satisfied.

---

## Prerequisites

- The enclave running (`make enclave-up`) — the trust store, the scheduler, the databases.
- Credentials in `.env`, including the identity provider's, as the other surface already needs.
- A credential of your own from that provider. **Not one this platform issues** — the surface
  verifies, it does not mint.

---

## 1. Bring the surface up

```
make mcp-surface-up
```

Brings up the served transport as its own job, separate from the supervisory loop. Both should
be running afterwards, and **stopping either must leave the other serving** — that separation
is FR-015a and it is the first thing worth confirming by hand.

**Expected**: the job reports healthy and the process logs that it is listening, having
constructed its collaborators. If it cannot reach the trust store or the stores, it must refuse
to start and say which one was missing (FR-003). A surface that starts degraded and answers
anyway is the failure this behaviour exists to prevent.

---

## 2. Confirm it is reachable from your machine

```
nc -z 127.0.0.1 <port> && echo reachable
```

**Expected**: reachable.

**Why this step is not a formality.** Measured on 2026-07-31, the API and portal are *not*
reachable from macOS — they run in host network mode, which on Docker Desktop is the Docker
VM's namespace and not your machine. `make portal-up` prints an instruction to open the portal
in a browser that cannot work today. This surface is built in bridge mode with a mapped port,
the way `postgres` already is, precisely so this step passes. If it does not, that is the
finding, not a misconfiguration on your side.

---

## 3. Attach a client

Configure your IDE with the address and your credential, or use the protocol SDK's own client.
The SDK client is what the conformance row drives; the IDE is what you actually want.

**Expected**: the session establishes, and asking what tools exist returns the platform's
operations — the same set the other surface exposes.

---

## 4. Call something, and read the trail

Call an operation you are entitled to. Then look at the audit trail for the record it wrote.

**Expected**: the record names **you**. Not the server, not a service account. If a colleague
does the same thing with their own credential, the trail distinguishes the two records.

**This is the one to check by hand even though a row covers it**, because it is the failure
that works perfectly. A server acting as itself would answer every call correctly, pass every
pre-existing check, and quietly convert a delegation chain into a shared account.

---

## 5. Watch it refuse (FR-017)

Present a credential that should not be able to do what you are asking, and call the operation.

**Expected**: refused — and the refusal is the governed core's, not the protocol layer's. Those
produce the same outcome from the client's seat, so confirming *where* it came from means
reading the audit trail or the server's own log, not just the client's error.

**Record what you see.** This demonstration goes in
[contracts/conformance.md](./contracts/conformance.md) with its output. A gate nobody has seen
fail is a gate nobody knows works.

---

## 6. Confirm the separation

```
# stop the served surface; the supervisory loop keeps running
# stop the supervisory loop; the served surface keeps answering
```

**Expected**: both. If stopping the transport stops the sweeper, suspended runs quietly stop
resuming — which presents as a hang and ends ADR-0049's guarantee that consent to start a run
is consent to finish it. That is FR-015a, and it is why these are two processes.

---

## What you have NOT proven

You have attached a client to a governed surface and watched governance work. **You have not
watched an agent decide anything.** The tool selection behind a dispatched run is still a
scripted round-robin (ROADMAP gap 0e).

This is stated here, at the end of a demonstration that will feel like the platform working,
because that is exactly when it stops being obvious.
