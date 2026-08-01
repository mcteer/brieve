<!-- SPDX-License-Identifier: Apache-2.0 -->
# Connecting a client to the MCP surface

Everything a client needs, from nothing. **If you have to read source to get through this,
that is FR-015 failing** — record what you had to look up.

---

## 1. Bring it up

```
make dev-up              # the trust store, the scheduler, the databases
DEV_IDP=1 make mcp-surface-up   # the served surface AND a development identity provider
```

**Two commands, not one.** `make dev-up` brings up the enclave only — the surfaces are kept
separate from it deliberately. `DEV_IDP=1` is what starts the development identity provider
alongside the surface; without it the surface uses the real provider from your `.env`.

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

**Credential: none that you handle.** The surface publishes
`/.well-known/oauth-protected-resource` naming its authorization server, which is the discovery
flow the MCP specification defines. A client follows it, registers itself, opens a browser, and
manages its own token — including renewing it.

So the editor entry is a URL and nothing else:

```json
{
  "mcpServers": {
    "brieve": { "url": "http://127.0.0.1:8083/mcp" }
  }
}
```

**No `headers`. No `Authorization`. No token.** If you find yourself pasting one into a config
file, something above has not come up — that is worth reporting rather than working around,
because a credential in a config file is a standing credential, which is the thing this platform
exists to avoid.

**Still not a credential this platform issues** — the surface verifies, it does not mint. Against
a real deployment the same flow runs against Auth0 or Okta; only the issuer configuration differs.

**If you need a token directly** — for a script, or to reproduce something without an editor —
`tests/conformance/mcp_served/surfaces.py::caller_token` walks the same flow and hands you one.
That path is unchanged and every automated lane still uses it.

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
