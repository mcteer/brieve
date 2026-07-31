# Conformance: Task-scoped authority manufacture

**Feature**: `specs/016-task-scoped-authority` | **Date**: 2026-07-31 | **Status**: Planned

The point of this contract is **who refuses**. Every row here turns on a refusal issued by
the trust store rather than by this platform's Python, because the property being bought is
that the boundary holds when the platform's own code is wrong. A row that asserted a refusal
our own enforcement produced would be re-testing Principle III's hooks, which already have
their own rows and already pass.

Rows live in `tests/conformance/authority/`, marked `enclave` and — where they drive the
scheduler or hold an operator token — `host_enclave`, wired into the Makefile's host lane
**in the same change that creates the directory**. 010 lost a feature's rows to a directory
no lane enumerated, and 014 lost ten more to a directory a lane named but deselected.

## The rows

| Row | Asserts | Via |
| --- | --- | --- |
| A task grant reaches what the task entails | A run whose tools entail path P can read P (SC-003 — zero false refusals) | Real grant, real Vault, real read |
| **A task grant refuses the rest of the ceiling** | The same run cannot read Q, which the definition's ceiling permits and the task does not (SC-001) | The refusal is Vault's; the row never calls the platform's own check |
| The refusal is the trust store's | Bypass the in-process hooks entirely and present the grant directly to Vault; Q is still refused (SC-002) | This is the row the feature exists for — it is the only one that distinguishes this work from what the hooks already do |
| A grant cannot exceed the ceiling | A grant naming a path outside the definition's ceiling is refused even though the grant names it (FR-003) | RAR ∩ entity policy — the intersection is restrictive in both directions |
| One decision per launch | A run performing many steps triggers exactly one authorization decision (SC-004) | Count exchanges against the issuer across a multi-step run |
| A person beyond their entitlements is refused at launch | Launch refuses and records, naming person and task (SC-005) | Read the trail through the evidence path |
| **A resumed run holds the same scope** | Disrupt mid-run; the resumed allocation's grant is byte-identical in scope to the launch grant (SC-006) | Kill and resume, compare the grants |
| **The grant record is not a credential** | The recorded grant, presented directly to the trust store, obtains nothing (SC-006a) | Present the record's bytes as a token; expect refusal |
| An expired grant stops rather than resumes | A run past its grant's expiry stops at a step boundary with nothing half-done (SC-007) | Existing grant-expiry machinery, asserted against the new grant |
| The posture names the arrangement in force | Federated, platform-issued, and absent each report as themselves, with a reason (SC-008) | Configure each; read the posture |
| Tool authority is unchanged | Tool decisions for the same run are identical before and after this feature (SC-009a) | Differential against the recorded trail |
| No new standing credential | The count of standing credentials is unchanged (SC-009) | The issuer holds a Vault token from its own attested identity and no key |
| **Only the issuer may mint task scope** | A workload other than the grant issuer is refused `transit/sign` on the signing key (FR-020) | The new privilege this feature creates — whoever holds it can manufacture authority, so it is bounded by policy and the bound is asserted rather than assumed |

## Break fixtures worth naming

- The grant is minted with the ceiling's paths instead of the task's → the "refuses the rest
  of the ceiling" row goes green while narrowing nothing.
- `jti` is dropped from the grant → **every** row fails with an indistinguishable 403, and the
  reason exists only in the Vault server log. This fixture exists to make that failure mode
  familiar before it is encountered under time pressure.
- The resume re-derives from the request rather than the record → scope drifts on resume and
  the "same scope" row catches it.
- A tool's `paths` declaration is widened to a wildcard → the grant stops narrowing, and the
  row that notices is the ceiling-remainder one rather than anything about manifests.
- The signing policy is widened to any authenticated workload → the "only the issuer may mint"
  row fails. Worth naming because the failure is silent otherwise: every other row still
  passes, since the grants they use are still correctly scoped.

## What these rows do not prove

- **That the narrowing is tight.** It is exactly as tight as the tools' path declarations
  (research F7). A run requesting a broadly-declaring tool gets a broad grant, and no row here
  says otherwise. What is asserted is the *relative* property: a subset of tools yields a
  subset of paths.
- **That a compromised allocation is contained.** The grant bounds what its token reaches; it
  does nothing about a process that has already obtained a different token by other means.
  The claim is "task scope is enforced somewhere the workload cannot reach", not "the workload
  is contained".
- **Tool authority.** This feature does not touch it (F6), and the row above exists to prove
  the absence of an effect rather than the presence of one.
- **Anything about the customer's IdP.** The federated tier is asserted against the dev
  enclave's own issuer standing in for one. Whether Okta, Ping, or IBM Verify will mint a
  custom RAR type is a deployment question no row in this repository can answer, and ADR-0056
  records that it was not established.

## Who runs these

| Where the change comes from | What covers these rows |
| --- | --- |
| Same-repo branch or pull request | CI's enclave lane (`make conformance`, host lane — wired with the directory's creation) |
| Fork pull request | The agent harness in the IDE, per `AGENTS.md` |

Per constitution v1.1.0, a blocking row no automated check executes needs a named runner.
Every row here runs in the enclave lane, so the automated runner covers them; none is owed a
human name.

**Sealed-core review**: this feature changes identity and authority flows, which Principle V
places in the sealed core and which require security-maintainer review before merge. **Dan
McTeer** holds that role. Recorded here rather than left to CODEOWNERS alone, because the
principle names the review and a contract that omitted it would be the same shape as a gate
whose only enforcement is everyone remembering.
