# Feature Specification: A browser login for the dev lane, so nobody pastes a credential

**Feature Branch**: `spec/023-dev-browser-login`

**Created**: 2026-08-01

**Status**: Draft

**Input**: Connecting an editor to the MCP surface required pasting an 800-character bearer token
into a config file by hand, and reminting it when it expired.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R2 / R3** (zero standing credentials, authority per task — a long-lived token in a config file is a standing credential, and the dev lane is where developers learn what the platform's identity model feels like). **None implicated in `src/`**: nothing shipped changes. |
| **ADRs touched** | **ADR-0033** (four transports over one authorization core — this changes neither; the surface's OAuth half already exists and is untouched). **ADR-0016 / ADR-0057** (claim mappings and the phrasing around them — a browser login produces the same claims the pasted token carried, and must not produce different ones). **None amended.** |
| **Evidence class** | **None.** No audit entry, no attestation input, no governed decision. This is development tooling: `tests/harness/dev_idp.py` and the scripts that start it. It ships in no deployment and appears in no trail. |

## What already holds, and what does not

**Holds, and more of it than expected.** Measured against the running service on 2026-08-01:

- **The surface already implements its half.** It serves `/.well-known/oauth-protected-resource`
  naming an authorization server — precisely the discovery the MCP specification defines. An editor
  was observed following it.
- **`/authorize` is a real browser endpoint.** It returns `302` with `code` and `state` to the
  client's `redirect_uri`. It is not a JSON test fixture wearing an endpoint's name.
- **`/token` performs a standard PKCE exchange**, and **PKCE is required rather than optional** —
  a missing or non-`S256` challenge is refused.
- **Against a real IdP this needs no code change at all.** The surface reads its issuer from
  configuration; pointed at Auth0 or Okta, a client does a browser login today. **This feature is
  about the development lane only.**

**Does not hold — three gaps, each measured rather than assumed:**

| Gap | How it was measured |
| --- | --- |
| **No `registration_endpoint`** | The discovery document omits it and no `/register` route exists. A client holding no pre-configured `client_id` has no way to obtain one (RFC 7591). |
| **`/.well-known/oauth-authorization-server` returns 404** | The IdP serves only the OpenID Connect path. The 404 was observed in the surface's own log, immediately after a client fetched the protected-resource document. |
| **The advertised issuer does not resolve for the client** | It is `http://host.docker.internal:8090` — correct for the surface, which runs in a container and must reach JWKS. Resolving that name from the host fails outright (`gaierror`). A client following the advertised authorization server cannot reach it. |

**The third is the interesting one**, because it is not an oversight. The issuer is a single value
serving two consumers with different network views: a container that must reach the host, and a
host process that must reach the same thing by a name it can resolve. Whatever is chosen has to
satisfy both, and "it works on my machine" is the failure mode this feature is most likely to ship.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A developer connects an editor without holding a credential (Priority: P1)

Someone runs `make dev-up`, points their editor at the MCP surface, and is taken to a browser to
sign in. The editor obtains and refreshes its own token. At no point do they see, copy, or store
one.

**Why this priority**: It is the whole feature. Everything else exists to make this work.

**Independent Test**: Configure an editor with a URL and no credential; connect; complete a browser
sign-in; call a governed operation successfully.

**Acceptance Scenarios**:

1. **Given** an editor configured with the surface's URL and **no** credential, **When** it
   connects, **Then** it discovers the authorization server, registers itself, and opens a browser
   for sign-in — with no manual step between.
2. **Given** a completed sign-in, **When** the editor calls a governed operation, **Then** it
   succeeds and the trail names the person who signed in, exactly as it would for a pasted token.
3. **Given** an expired token, **When** the editor next calls an operation, **Then** it renews
   without the developer being involved. **The absence of a re-paste step is the point.**

---

### User Story 2 - The claims are the same ones the pasted token carried (Priority: P1)

A token obtained by browser login must map to the same roles, tenant, and subject as one minted
directly. If it does not, the dev lane teaches a different identity model than the one the platform
enforces.

**Why this priority**: Equal-first, and easy to lose. A login that quietly grants broader or
narrower claims than the conformance rows use would make every hand-driven check disagree with the
automated ones — and the hand-driven one is the one a person trusts.

**Independent Test**: Sign in through the browser and mint directly; compare what the surface makes
of each.

**Acceptance Scenarios**:

1. **Given** a browser sign-in and a directly minted token for the same subject, **When** each calls
   the same operation, **Then** the surface resolves the same subject, tenant, and roles.
2. **Given** claims that map to no role, **When** a browser sign-in produces them, **Then** the
   surface refuses exactly as it does today. **The login must not be able to produce only
   well-mapped claims** — a harness that cannot present a bad one cannot show the platform
   refusing it.

---

### User Story 3 - The advertised authorization server is reachable by everyone who is told about it (Priority: P1)

A client follows the discovery document it was given and reaches the authorization server. So does
the surface, from inside its container, for the keys it verifies with.

**Why this priority**: P1 because it blocks US1 entirely — a client that cannot resolve the
advertised host never reaches a sign-in page. Listed separately because it is the one gap that is
not "add a missing endpoint", and the one most likely to be solved in a way that works for whoever
tested it and no one else.

**Independent Test**: From the host and from inside a container, reach the advertised issuer and
fetch its keys.

**Acceptance Scenarios**:

1. **Given** the discovery document the surface publishes, **When** a process on the host follows
   the authorization server URL, **Then** it reaches the provider.
2. **Given** the same document, **When** the surface inside its container fetches the keys,
   **Then** it reaches the same provider and the tokens verify.
3. **Given** a token minted before the surface restarted, **When** it is presented afterwards,
   **Then** the outcome is stated — this is where the existing signing-key trap lives (see Edge
   Cases), and the feature must not make it quieter.

---

### Edge Cases

- **The provider restarts.** It mints a new signing key per process while keeping the same key
  identifier, so every outstanding token becomes unverifiable and the surface — which reads keys at
  startup — must also restart. The refusal names the symptom (`unverifiable_identity`) and not the
  cause. This cost several minutes on 2026-08-01, and a browser login makes it *more* likely to be
  hit, because tokens will be longer-lived and used across restarts.
- **A client registers more than once.** Editors re-register on reconnect. Whether that is idempotent, or accumulates registrations, or refuses, must be stated rather than discovered.
- **Two developers, or two editors, at once.** Whether concurrent logins interfere.
- **The browser flow is abandoned.** Someone opens the sign-in and closes the tab. Whether the
  client can retry, and whether anything is left behind.
- **A pasted token is still supplied.** Configurations exist with one in them. Whether it keeps
  working, or is refused, or is ignored in favour of the flow.
- **A redirect target that is not the client's.** The provider authenticates nobody by design; it
  must still not redirect a code to an arbitrary address supplied by whoever asked.

## Requirements *(mandatory)*

### Functional Requirements

**The outcome**

- **FR-001**: A developer MUST be able to connect an editor to the MCP surface holding **no
  credential**, complete a browser sign-in, and call governed operations.
- **FR-002**: The developer MUST NOT be required to see, copy, paste, or store a token at any point,
  including on renewal.
- **FR-003**: `make dev-up` MUST be sufficient. A login that requires a further undocumented step is
  the same gap with more instructions.

**Discovery**

- **FR-004**: The provider MUST answer the discovery path an MCP client actually requests, in
  addition to the one it already serves. The set MUST be determined by what clients request, not by
  what the specification permits — the 404 that motivated this was observed in a log, not inferred.
- **FR-005**: The provider MUST offer client registration, so a client holding no pre-configured
  identifier can obtain one.

**Reachability**

- **FR-006**: The authorization server named in the surface's discovery document MUST be reachable
  **both** from the host and from inside the surface's container, using the single name that
  document publishes.
- **FR-007**: The surface MUST continue to verify tokens against that provider from inside its
  container. **A change that makes the client's path work by breaking the surface's is a
  regression**, and both directions MUST be checked rather than one asserted from the other.

**Fidelity to the platform's identity model**

- **FR-008**: A token obtained by browser login MUST resolve to the same subject, tenant, and roles
  as one minted directly for the same person.
- **FR-009**: The login MUST remain able to produce claims that map to **no** role, so the
  platform's refusal stays demonstrable. A harness that can only produce well-formed identities
  cannot distinguish a working platform from a broken one.
- **FR-010**: PKCE MUST remain required, and MUST NOT become optional in the course of making the
  flow more convenient.
- **FR-011**: The provider MUST NOT redirect an authorization code to a target it was simply handed
  by the requester without constraint. It authenticates nobody; that is not a reason for it to hand
  credentials anywhere it is pointed.

**Boundaries**

- **FR-012**: **Nothing under `src/` may change.** This feature is development tooling. If a change
  to shipped code appears necessary, that is a different feature and MUST be raised rather than
  absorbed.
- **FR-013**: The provider MUST remain unmistakably development-only, carrying its existing
  warnings, and MUST NOT become closer to something deployable in the course of becoming more
  standards-complete.
- **FR-014**: The existing direct-mint path MUST keep working. Conformance rows and scripts depend
  on it, and replacing it would trade a paste for a browser step in every automated lane.

### Key Entities

- **Registered client**: An editor that has obtained an identifier from the provider. Holds no
  secret it did not generate.
- **Discovery document**: What the provider publishes about where to authorize, exchange, and fetch
  keys. Must be true from every network position it is published to.
- **Advertised issuer**: The single name the surface publishes and both consumers resolve. The
  feature's hardest constraint, because two consumers see the network differently.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer connects an editor and reaches a working session with **zero** credential
  handling steps — measured by a written procedure containing no copy, paste, or token.
- **SC-002**: The procedure works from a clean start: `make dev-up`, configure, connect, sign in,
  call an operation. Demonstrated end to end against the running service, not a test double.
- **SC-003**: A token from browser login and one minted directly resolve to the same subject,
  tenant, and roles.
- **SC-004**: Claims that map to no role are still producible through the login, and the surface
  still refuses them.
- **SC-005**: The advertised issuer resolves and answers from **both** the host and inside the
  surface's container — both checked, neither inferred.
- **SC-006**: Every existing conformance row that used a directly minted token still passes,
  unchanged.
- **SC-007**: No file under `src/` differs.
- **SC-008**: A session survives token renewal without developer involvement.
- **SC-009**: The signing-key restart trap either no longer occurs, or produces a message naming the
  cause rather than the symptom. **Silence is not an acceptable outcome here** — it is the failure
  this feature makes more likely.

## Assumptions

- **The client is an editor speaking MCP.** Cursor is the one measured. Others are expected to
  follow the same discovery, and any that does not is out of scope rather than a defect.
- **Real-IdP deployments need nothing.** The surface reads its issuer from configuration and the
  OAuth half already works; pointing it at Auth0 or Okta gives a browser login today. **This is
  asserted from reading the configuration path, and is worth confirming before it is repeated as
  fact** — the last three things asserted that way in this repository turned out to be false.
- **The provider authenticates nobody, and still will.** It is quarantined in `tests/` for that
  reason. Becoming more standards-complete must not soften it.
- **No new dependency.** The provider is standard-library only, and staying that way is assumed.
- **The gaps are exactly three.** Measured on 2026-08-01 against a running service. A fourth
  emerging during implementation is expected rather than surprising — this list came from following
  one client, and a second client may reveal more.
