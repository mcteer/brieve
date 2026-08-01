# Implementation Plan: A browser login for the dev lane, so nobody pastes a credential

**Branch**: `spec/023-dev-browser-login` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/023-dev-browser-login/spec.md`

## Summary

A developer connecting an editor to the MCP surface must paste an 800-character token into a config
file and remint it when it expires. The surface's OAuth half already works; the gap is entirely in
the development identity provider and the scripts that start it.

**This is smaller than it looked when it was offered.** Research narrowed it to three additions and
one deletion, none of them under `src/`:

- Serve the existing discovery document at the **second path clients actually probe**.
- Add a **registration endpoint** that holds no state.
- Mint a **distinct key id per process**, which removes the restart trap by letting the surface's
  own refetch path work.
- **Delete a derivation**: `mcp-surface-up` computes the JWKS URI from the issuer, welding together
  two values the platform deliberately keeps apart.

`/authorize` and `/token` are not touched. Both were read in full: the first genuinely redirects
with `code` and `state`, the second performs a real PKCE `S256` exchange and refuses a bad
challenge.

## Technical Context

**Language/Version**: Python 3.12, standard library only in the provider.

**Primary Dependencies**: **None added.** `tests/harness/dev_idp.py` uses `http.server`; the
provider's crypto is the existing `FakeOIDCProvider`.

**Storage**: None. Registration holds nothing (research F5).

**Testing**: pytest — the served-surface conformance lane (`tests/conformance/mcp_served`), plus
hermetic rows over the provider's HTTP surface.

**Target Platform**: A developer's machine. The surface runs in a container under Nomad; the
provider runs on the host.

**Project Type**: Development tooling for a governed agent runtime. Ships in no deployment.

**Performance Goals**: None. The only timing that matters is a browser round-trip, bounded by a
human.

**Constraints**: **Nothing under `src/` may change** (FR-012). No new dependency. The provider must
remain unmistakably development-only (FR-013). PKCE stays required (FR-010). The direct-mint path
keeps working, because every automated lane depends on it (FR-014).

**Scale/Scope**: One file (`tests/harness/dev_idp.py`), one or two scripts under `infra/bin/`. Two
new HTTP routes, one changed constant, one deleted line.

## Constitution Check

*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Nothing enters core. The provider is standard-library HTTP and stays that way. |
| II — Total Interception; One Governed Tool Layer | **N/A** | No tool, hook, registry, or governed operation is touched. |
| III — Fail-Closed, In-Process Enforcement | **Pass, and worth watching.** | The surface's refusals cannot change — no `src/` change is permitted. The risk here is the opposite of weakening: a provider that becomes easier to authenticate against must not become one that produces only well-mapped claims. FR-009 forbids that, because a harness unable to present a bad identity cannot show the platform refusing one. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass, and it is the point.** | A long-lived token in a config file *is* a standing credential. Replacing it with a flow the client renews applies the principle to the lane where developers form their intuitions. **The rejected alternative mattered**: persisting the provider's keypair would put a private key on disk to keep old tokens alive — the same instinct this principle exists to refuse. |
| V — Sealed Core, Versioned Seams | **N/A** | No sealed-core file is touched: no audit event type, no schema, no registry, no adapter. **No security review is owed** — stated explicitly because the previous three features each owed one, and an absence should be asserted rather than inferred from silence. |
| VI — Lean by Default | **Pass, strongly.** | No dependency, no service, no store. The largest single change is deleting a line that derived one config value from another. |
| VII — Anti-Fragmentation | **Pass** | The second discovery path serves the **same document body** as the first rather than a parallel one. Two bodies could drift; one cannot. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **N/A** | No model, judge, pack, or policy. `OWED` stays empty. |
| IX — Evidence Over Claims | **Pass** | No evidence path changes. The feature's own claims were measured before being written, and two corrected statements this repository already carried (research F2, F3). |
| X — The Decision Record Governs | **Pass, no amendment.** | ADR-0033's parity guarantee is untouched — no surface behaviour changes. ADR-0016/0057 on claim mappings are **consumed**: a browser login must resolve to the same subject, tenant, and roles as a minted token (FR-008), a constraint those decisions already impose. |

**Gate result**: **PASS — proceed to Phase 0.**

**No obligations created.** No security review, no ADR amendment, no named runner for an
unautomated blocking row. That is unusual for this repository, and it is recorded plainly so that
nobody goes looking for one that does not exist.

**What the gate does bind**: SC-002 and SC-009 are written to be verified against the running
service. This feature exists because pasting a credential is what *using* the platform actually
felt like; a version demonstrated only against a test double would reproduce the mistake it was
written about.

## Project Structure

### Documentation (this feature)

```text
specs/023-dev-browser-login/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── conformance.md   # Phase 1 — the rows this feature binds
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
tests/harness/
└── dev_idp.py                    # +2 routes, +1 discovery field, per-process key id

infra/bin/
├── mcp-surface-up                # STOP deriving OIDC_JWKS_URI from OIDC_ISSUER
└── mcp-surface-conformance       # issuer becomes host-resolvable; JWKS stays container-reachable

tests/conformance/mcp_served/
└── ...                           # rows over both discovery documents and registration

src/
└── (unchanged — SC-007 asserts this)
```

**Structure Decision**: everything lives in `tests/harness/` and `infra/bin/`, which is what makes
the Constitution Check as quiet as it is. The feature's risk profile follows directly: it cannot
break a deployed system, and it can very easily produce a lane that works only on the machine it
was written on.

**The one architectural point is negative.** `infra/bin/mcp-surface-up:54` computes
`OIDC_JWKS_URI="${OIDC_ISSUER_OVERRIDE}/jwks"`. `served.py:166-167` treats those as independent —
an identity to compare and a location to fetch — and the script reintroduces a coupling the
platform does not have. Removing it is what makes clarify's answer possible, and it is a deletion
rather than an addition.

## Constitution Re-Check (post-Phase 1)

**Re-evaluated after `data-model.md`, `contracts/conformance.md`, and `quickstart.md`. Still PASS;
no verdict moved.** Phase 1 added no dependency, no state, and no `src/` change.

One emphasis changed. **Principle III's watch item is now the feature's sharpest row**: the
registration endpoint accepts anyone, and the temptation while making a login *work* is to have it
always produce a claim set that maps cleanly. FR-009 forbids exactly that, and `data-model.md`
carries the constraint into the registration record so it is visible where someone would otherwise
simplify it away.

## Complexity Tracking

*No Constitution Check violations. Table intentionally empty.*

One judgment call, recorded because it could reasonably have gone the other way:

| Decision | Why | Alternative rejected because |
|---|---|---|
| Per-process key **id** rather than a persisted keypair | Removes the restart trap through the surface's existing refetch-on-unknown-id path, with no `src/` change | Persisting keeps old tokens alive, but writes a private key to disk and solves a smaller problem — a browser client re-authenticates on its own, so a dead token costs nothing |
