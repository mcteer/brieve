<!-- SPDX-License-Identifier: Apache-2.0 -->
# Signing in against a real identity provider

The platform federates attribution to the customer's OIDC provider, always. It is the
only party that can say who the human is. This describes pointing the surfaces at one —
Auth0 in the worked example, because that is what was used to prove the path, but nothing
here is Auth0-specific except where it says so.

## What the provider has to supply

Three things, and **no provider emits all three by default**.

| | Why | Refusal if missing |
|---|---|---|
| A JWT for a named **audience** | The API verifies `aud` | `unverifiable_identity` |
| A **tenant** claim | Tenant isolation | `no_tenant` |
| A **role-bearing** claim | Which claim maps to which role | `unmapped_claim` |

The refusals are deliberately distinct. An operator debugging an integration needs to
tell "your token is bad" from "your claim is not mapped", and both refuse identically
without the distinction.

### Audience

The single most confusing failure. Auth0 issues an **opaque token** — not a JWT at all —
when the authorization request names no audience, and the API then refuses it as
`unverifiable_identity`. That error names the token, so the natural next step is to
inspect the token, the JWKS and the signing algorithm, none of which are wrong.

The portal forwards `OIDC_AUDIENCE` on the authorization request. Set it to the API's
identifier, **not** to a client id. `portal-up` refuses to start without it when a real
provider is configured, for exactly this reason.

### Tenant

There is no provider-neutral claim name. Auth0, Okta and Ping all refuse to mint an
un-namespaced custom claim, so a real deployment carries something like
`https://example.com/tenant` and `OIDC_TENANT_CLAIM` names it.

Do not give this a fallback value in the provider. A token with no tenant must be
refused; an identity provider that supplied a default would place a user nobody assigned
to a tenant into whichever tenant that default named.

### Roles

Roles are **not** granted by the provider. The provider says which claims a person
carries; the platform decides what those claims are worth, and that decision is an
authority change gated by quorum (ADR-0016). Submitting a mapping goes through
`POST /authority/claim-mappings`; nothing takes effect until the Control Group approves.

So a correctly configured provider plus an estate that has approved no mappings produces
a successful sign-in and a `403 unmapped_claim` on the first request. That is the
mechanism working.

## Auth0 specifically

### An API, which is where the audience comes from

Create one (Applications → APIs). Its **identifier** is the audience — a URI, and it does
not have to resolve.

Turn on **RBAC** and **Add Permissions in the Access Token**. Auth0 then puts the user's
assigned permissions in a top-level `permissions` array, which `resolve_roles` already
handles because it accepts list-valued claims. **This means roles need no Action.** Map
them directly:

```
claim_name: permissions   claim_value: platform:operator   role: operator
```

### An Action, for the tenant only

Auth0 has no native tenant claim, so this is the one thing that needs custom code. Have
it read `app_metadata` and set nothing when the field is absent:

```js
exports.onExecutePostLogin = async (event, api) => {
  const tenant = event.user.app_metadata && event.user.app_metadata.tenant;
  if (tenant) {
    api.accessToken.setCustomClaim("https://example.com/tenant", tenant);
  }
};
```

Do not have it write roles as well. The API already supplies those, and a second source
of the same fact disagrees with the first the moment somebody changes one of them.

Machine identities need a second Action on the `credentials-exchange` trigger, reading
`event.client.metadata` — `client_credentials` has no user, so no post-login trigger
fires, and a machine belongs to a tenant exactly as a person does.

### An application for the portal — public, with no secret

`token_endpoint_auth_method: "none"`. The portal is a **public client using PKCE**, and a
confidential one would need a secret in its jobspec, which is the standing credential
Principle IV prohibits without exception. Auth0's "Regular Web Application" default is
confidential; either pick a SPA or set the auth method explicitly.

### The trailing slash

Auth0's `iss` claim is `https://TENANT.auth0.com/` **with** a trailing slash. A verifier
configured without it refuses every token as `unverifiable_identity` — the same error as a
bad signature, for one character of configuration.

## Configuring the enclave

`portal-up` reads `.env`. Name an `AUTH0_DOMAIN` and it uses the real provider; leave it
out and it starts the development double, which **authenticates nobody**. It says which
one it chose on every run, because an operator who believed they were federated when they
were not is the unstated posture this platform legislates against everywhere else.

```
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_API_AUDIENCE=https://api.example.com
AUTH0_PORTAL_CLIENT_ID=...            # public client — there is no secret to put here
OIDC_TENANT_CLAIM=https://example.com/tenant
```

## Checking it before involving a browser

A machine token exercises the whole verification path — signature against the live JWKS,
issuer, audience, tenant, claim-to-role — without a login flow:

```
curl -s -X POST "https://$AUTH0_DOMAIN/oauth/token" \
  -H 'content-type: application/json' \
  -d '{"client_id":"...","client_secret":"...","audience":"'$AUTH0_API_AUDIENCE'","grant_type":"client_credentials"}'
```

Decode the result and confirm `permissions` and the tenant claim are both present. If the
token is not three dot-separated segments, the audience is missing or wrong — that is the
opaque-token case above, and no amount of looking at the verifier will show it.
