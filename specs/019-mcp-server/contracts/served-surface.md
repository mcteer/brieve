<!-- SPDX-License-Identifier: Apache-2.0 -->
# Contract: the served surface

What a client attaching to this platform may rely on. Written for whoever configures a client,
and for whoever changes the server later and needs to know what they may not break.

---

## What the client does

1. **Presents a credential.** A bearer token from the identity provider the platform verifies
   against — the same one the other surface accepts. Not a credential this platform issues.
2. **Establishes a session.** The server resolves the credential to a subject and pins it.
   No acceptable credential means no session (FR-012).
3. **Asks what operations exist.** The set matches the other surface's, mechanically (FR-008).
4. **Calls operations.** Each one is governed, recorded, and answered.

---

## What the surface guarantees

**Every operation goes through the governed core.** There is no protocol-layer shortcut to any
capability. A refusal is the core's decision reported by the protocol layer, never the protocol
layer's own (FR-005, FR-006).

**Every operation executes as the calling user.** Never as the server, never as a shared
account. The audit trail names the person who called (FR-009, FR-010), and two callers doing
the same thing are distinguishable in it (FR-011).

**Authority is re-checked on every operation.** A session established with a valid credential
stops serving operations once that credential is no longer valid. The session's *subject* does
not change when this happens — the *operation* is refused (FR-013, FR-013a).

**Failures are distinguishable.** Refused, unknown operation, and transport failure are three
different answers, because they call for three different responses (FR-007).

**The surface is up or it is plainly down.** It refuses to start rather than start degraded
(FR-003). A surface that accepted connections while unable to record evidence would be worse
than one that is visibly absent.

---

## What the surface does NOT guarantee

Stated here and not only in the conformance contract, because this is the document someone
reads before connecting, and a limit recorded only where nobody lands is not recorded.

**No model is choosing anything.** This serves the transport. A dispatched run still selects
tools by a scripted sequence (ROADMAP gap 0e). Attaching a client and watching governance run,
refusals refuse, and evidence get written is the platform working — and it is *not* evidence
that an agent made a decision, because none did.

**No new operations.** The set is what the transport already defines. This feature serves it;
it does not extend it.

**Not a public API.** One developer's IDE against their own enclave. It carries no rate
limiting, no quota, no tenancy separation beyond what the core already applies.

---

## What must not change without a new decision

- **The operation set stays equal to the other surface's.** They are compared mechanically;
  changing one alone is a gate failure, which is ADR-0033's parity guarantee doing its job.
- **The subject stays the caller's.** Any change that lets the server act as itself, or lets a
  request carry its own subject, breaks the delegation chain and does so invisibly.
- **The supervisory loop stays independently available.** A future change that merges the two
  processes re-creates the failure FR-015a forbids: a protocol crash silently stopping
  suspended runs from resuming.
