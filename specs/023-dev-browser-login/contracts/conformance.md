<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 023 — a browser login for the dev lane

What these rows assert, what they refuse to assert, and who runs them.

---

## Who runs these rows

**Most of this is hermetic**, because the provider is an HTTP server on the host: its discovery
documents, registration endpoint, and per-process key id can all be checked by starting it and
making requests. No enclave, no container, no browser.

| Group | Where | Needs |
| --- | --- | --- |
| Both discovery paths return one body; registration answers; PKCE still required | `tests/conformance/mcp_served/` | The provider only |
| A distinct key id per process, and prompt refusal of a previous process's token | `tests/conformance/mcp_served/` | The provider only |
| The surface reaches the keys from inside its container while the client resolves the issuer | `tests/conformance/mcp_served/` | The served surface — `infra/bin/mcp-surface-conformance` |
| **The browser flow itself, end to end** | By hand | A person, a browser, an editor |

**The last row cannot be automated and is the one that matters.** SC-002 is written as a procedure
containing no copy, paste, or token, performed from a clean start. A person is the only thing that
can confirm a browser login *felt* like a login.

| | What it is | Who | Status |
| --- | --- | --- | --- |
| The end-to-end browser login | `make dev-up`, configure an editor with no credential, connect, sign in, call an operation | **Dan McTeer** | **Owed** |

**No security review is owed** and **no ADR amendment is owed.** Stated because the previous three
features each owed at least one, and a reader scanning for the pattern should find its absence
asserted rather than have to infer it.

---

## What these rows assert

**One document, two paths.** `/.well-known/openid-configuration` and
`/.well-known/oauth-authorization-server` return the same body. The second exists because a client
requested it and got a 404 — measured in the surface's log, not inferred from a specification.

**Registration answers, repeatably.** A client with no identifier obtains one, and asking again
succeeds. Editors re-register on reconnect; a provider that errored on the second attempt would
work once per developer.

**A redirect target is constrained.** The provider authenticates nobody and still refuses to send
an authorization code to an arbitrary address.

**PKCE is still required.** A missing or non-`S256` challenge is refused. This is asserted rather
than assumed precisely because the feature's direction is *making the flow easier*.

**The key id differs per process, and a stale token is refused promptly.** Restart the provider,
present a token from before, and the refusal arrives immediately rather than after a cache window.
Verified by restarting and calling — not by reasoning about cache behaviour, which is how the wrong
explanation of this survived twice.

**The client's name and the surface's name both work.** A process on the host resolves the
advertised issuer; the surface inside its container fetches keys by a name it can resolve. **Both
checked. Neither inferred from the other** — that inference is the failure this feature is most
likely to ship.

**The identity is unchanged.** A token from a browser login and one minted directly resolve to the
same subject, tenant, and roles.

**A bad identity is still producible.** Claims that map to no role can still be presented, and the
surface still refuses them.

**Nothing under `src/` differs.**

---

## What these rows refuse to assert

**They do not assert that a real IdP works.** The claim that pointing `OIDC_ISSUER` at Auth0 or
Okta gives a browser login with no code change is read from the configuration path and **has not
been run**. It is the most repeatable-sounding sentence in this feature and the least verified; it
is flagged in the spec's Assumptions for that reason and must not be quoted as measured.

**They do not assert that every MCP client works.** One editor was measured. Another that discovers
differently is out of scope rather than a defect — and would be worth a look, since this feature's
gap list came from following exactly one client.

**They do not assert that the provider is secure.** It authenticates nobody. Nothing here makes it
safer, and the rows must not be read as evidence that it could be exposed.

**They do not assert anything about the platform's authorization.** No governed operation, refusal,
or audit record changes. A green row here says a developer can obtain a token, not that the token
grants anything it should not.

---

## The row that would have caught the original problem

There isn't one, and that is worth saying plainly rather than inventing a claim.

The problem was never a defect a check could fail on: every component behaved as written, the
served-surface rows passed, and the platform refused nothing it should have allowed. What was
missing was that **nobody had connected an editor without a credential and tried to sign in**. The
gap was in the experience, and the only thing that surfaces that is the hand-performed row above —
which is why it is owed by name rather than waived as unautomatable.
