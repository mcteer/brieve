<!-- SPDX-License-Identifier: Apache-2.0 -->
# Connecting a client to the MCP surface

Everything a client needs, from nothing. **If you have to read source to get through this,
that is FR-015 failing** — record what you had to look up.

---

## 1. Bring it up

```
make enclave-up          # the trust store, the scheduler, the databases
make mcp-surface-up      # the served surface, on its own job
```

The surface announces itself:

```
mcp surface ready — role=mcp-surface operations=16 db=host.docker.internal
Uvicorn running on http://0.0.0.0:8083
```

If it refuses to start it names what was missing. That is deliberate: a surface that started
without an issuer would verify tokens against nothing and look healthy.

---

## 2. Confirm it reaches your machine

```
nc -z 127.0.0.1 8083 && echo reachable
```

**Not a formality.** Measured on 2026-07-31, the API and portal were *not* reachable from
macOS — they run in host network mode, which on Docker Desktop is the Docker VM's namespace
and not your machine, and the port block declared beside it is inert. This surface is built in
bridge mode with a mapped port, the way `postgres` already is, so this step passes. If it does
not, that is the finding rather than a misconfiguration on your side.

---

## 3. Point a client at it

**Address**: `http://127.0.0.1:8083/mcp` — Streamable HTTP.

**Credential**: a bearer token from the identity provider the platform verifies against, sent
as `Authorization: Bearer <token>`. **Not a credential this platform issues** — the surface
verifies, it does not mint. The same provider the portal signs people in against.

For an IDE, that is an MCP server entry with the URL above and an `Authorization` header.

---

## 4. What you should see

- **No credential** → `401 {"error": "invalid_token"}`. Refused before any operation is
  entered.
- **A token that maps to no role** → refused. That is the mechanism working: claims reach the
  platform through a mapping that clears a Control Group, and until one exists you are
  entitled to nothing.
- **A mapped token** → the operations list, and calls that answer with the core's verdict.

Four failures are distinguishable on purpose — **refused**, **unknown operation**,
**malformed request** (naming the field you left out), and **transport failure**. They call
for four different responses, and a surface that collapsed them would make every denial look
like a broken platform.

---

## What this is NOT

**No model is choosing anything.** This serves the transport. A dispatched run still selects
its tools by a scripted sequence (ROADMAP gap 0e). Attaching a client and watching governance
run, refusals refuse, and evidence get written is the platform working — and it is **not**
evidence that an agent made a decision, because none did.

Stated here, at the end of a walkthrough that will feel like more than it is, because that is
exactly when it stops being obvious.
