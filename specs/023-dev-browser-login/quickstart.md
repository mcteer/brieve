<!-- SPDX-License-Identifier: Apache-2.0 -->
# Quickstart: 023 — proving nobody has to paste a credential

**The last scenario is the feature.** Everything above it can pass while a developer still ends up
copying a token, which is exactly the state this exists to end.

---

## Prerequisites

```bash
make dev-up
docker run --rm --privileged alpine hwclock -s   # VM clock drift breaks attestation
```

---

## 1. Both discovery paths, one body

```bash
curl -s http://127.0.0.1:8090/.well-known/openid-configuration      > /tmp/a
curl -s http://127.0.0.1:8090/.well-known/oauth-authorization-server > /tmp/b
diff /tmp/a /tmp/b && echo "identical"
```

**Expect**: identical, and both containing `registration_endpoint`.

**Before this feature the second path returned 404** — observed in the surface's own log
immediately after a client fetched the protected-resource document. That 404 is why an editor could
discover the authorization server and get no further.

---

## 2. A client can obtain an identifier

```bash
curl -s -X POST http://127.0.0.1:8090/register \
  -H 'Content-Type: application/json' \
  -d '{"redirect_uris":["http://127.0.0.1:33418/callback"]}'
```

**Expect**: a `client_id`. **Run it twice** — the second must succeed too, because editors
re-register on reconnect.

**Then try to break it**: register a redirect target that is not a loopback address. It must be
refused. The provider authenticates nobody, and that is not a reason to hand an authorization code
to any address it is given.

---

## 3. PKCE is still required

```bash
curl -s "http://127.0.0.1:8090/authorize?redirect_uri=http://127.0.0.1:1/cb&state=x"
```

**Expect**: refused for a missing challenge. Asserted rather than assumed because this feature's
whole direction is making the flow easier, and "just for dev" is how a requirement becomes
optional.

---

## 4. The restart trap is gone

```bash
curl -s http://127.0.0.1:8090/jwks | python3 -c "import sys,json; print(json.load(sys.stdin)['keys'][0]['kid'])"
# restart the provider, then:
curl -s http://127.0.0.1:8090/jwks | python3 -c "import sys,json; print(json.load(sys.stdin)['keys'][0]['kid'])"
```

**Expect**: two different key ids.

**Then present a token from before the restart.** It must be refused **immediately** — not after a
ten-minute window, and **without restarting the surface**.

**Why this works, since the repository twice said otherwise**: `verification.py` caches keys with a
600-second TTL and refetches on an id it does not recognise. The trap existed only because the
provider reused `test-key-1`, so a still-fresh cache returned the old modulus. A distinct id per
process makes the surface refetch on the spot. **No `src/` change.**

---

## 5. Both names reach the provider

```bash
curl -s -o /dev/null -w "host  -> %{http_code}\n" http://127.0.0.1:8090/jwks
docker run --rm curlimages/curl -s -o /dev/null -w "container -> %{http_code}\n" \
  http://host.docker.internal:8090/jwks
```

**Expect**: both `200`.

**Check both. Never infer one from the other** — that inference is the single most likely way this
feature ships working only on the machine it was written on.

---

## 6. The one that is the feature

**By hand. A browser. No credential anywhere.**

1. `make dev-up`
2. Configure an editor with **only** the surface's URL:

   ```json
   { "mcpServers": { "brieve": { "url": "http://127.0.0.1:8083/mcp" } } }
   ```

   **No `headers`. No `Authorization`. No token.**
3. Connect. A browser opens. Sign in.
4. Ask the editor to list runs.

**Expect**: it answers, and the trail names the person who signed in.

**Then wait for the token to expire and ask again.** It must keep working with no involvement from
you. *The absence of a re-paste step is the whole point.*

**This is the row that cannot be automated**, and the only one that would have caught the original
problem — which was never a defect a check could fail on. Every component behaved as written and
the served rows passed; nobody had tried to connect without a credential.

---

## Definition of done

- Scenarios 1–5 pass, run from a clean start
- Scenario 6 performed by hand — **owed, named in the conformance contract**
- `make check` green; **no file under `src/` differs** (SC-007)
- Every conformance lane that used a directly minted token still passes, unchanged (FR-014)

**Nothing else is owed.** No security review, no ADR amendment — unusual here, and stated so nobody
looks for one.
