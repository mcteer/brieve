# ADR-0062: The authoring credential is vended per task, and is Principle IV's third exception

- **Status**: Proposed
- **Date**: 2026-08-05
- **Amends**: Principle IV of the constitution (the enumerated exception list)
- **Relates to**: [ADR-0038](0038-integration-uplift-workflows.md), [ADR-0044](0044-authz-doctrine-and-credential-translation.md), [ADR-0058](0058-model-credential-brokering.md), [ADR-0042](0042-duplicate-detection-and-precedent-cache.md)
- **Requirements**: R2, R3

## Context

[ADR-0038](0038-integration-uplift-workflows.md) makes the pull request the thing that keeps the
integration-and-uplift family safe to offer: *"writes land exclusively as pull requests,
scoped to the requester's own repositories, with the human as merge authority."* Building
that (038) reaches a question the record did not face, because in 2026-07 the family was a
decision rather than an implementation.

**A run that opens a pull request must authenticate as something, and this platform holds
nothing it could use.** Measured across `src/`, `infra/` and `.github/`: there is no
version-control credential anywhere. Every credential path resolves through
`core/durability/credentials.py` — an allocation logs into Vault as its own attested
workload identity and takes something short-lived.

037's precedent does not transfer. Its proposal is opened by **CI**, which holds a token by
virtue of being CI. A run holds nothing.

033 already met the adjacent question and refused the obvious answer, recording the
consequence rather than acquiring a credential to hide it: *"The usual fix is a personal
access token; this platform does not hold one, because a long-lived credential is exactly
what Principle IV refuses."* That refusal stands. What 033 did not need, and 038 does, is a
credential a **run** can hold.

**And Principle IV's exception list is closed.** It reads: *"The enclave holds no standing
credentials to anything it manages — with exactly two named exceptions, both rotated and
Control-Group-governed: the management token behind the TFE broker (ADR-0044), and the model
vendor credential behind the model broker (ADR-0058)."* A version-control App private key
held in the trust store is a **third**.

## Decision

**The authoring credential is a version-control App installation token, vended per task from
the trust store under the reading workload's own attested identity — and it is named as
Principle IV's third exception, in the same change.**

- The App **private key** is held in the control-plane Vault and nowhere else. No workload
  persists it; no jobspec carries it; it is read under attested identity like the other two.
- What a run receives is an **installation token**: hour-scoped, and **installation-scoped to
  the requester's own repositories**. It is minted per task and evaporates with it.
- **The key is never mounted into the hardened tier.** The step that reads hostile content
  holds no credential that could publish; the step that publishes never reads the subject.
  That separation is a fact about which task holds what, not a promise about behaviour.
- The exception inherits every condition the other two carry: rotated, Control-Group-governed,
  trust-store only, read under the reading workload's own attested identity, delivered per
  task, never persisted.
- **The constitution is amended in the same change.** Principle X: where a document conflicts
  with an Accepted ADR, the ADR wins and the document is amended alongside it.

## Consequences

The platform can do the thing its own description claims — author an integration and open a
pull request — under a credential story that matches every other credential story it has.

**The alternative readings were available and are worse.** One could argue the clause does not
bite, since it bounds credentials *"to anything it manages"* and the platform does not manage
the requester's repository. That reading is real and it is the narrowing **027 declined** when
the model vendor credential arrived: it amended the constitution and the
`test_no_static_credentials` gate in the open, and recorded why renaming a field to dodge the
matcher was rejected — *"a gate that passes by vocabulary is worse than no gate."* A closed
list that grows by interpretation is not a closed list.

The cost is a third exception, and exceptions compound: the argument for a fourth is easier
than the argument for this one was. That is the real price, and it is paid deliberately rather
than avoided by wording.

**What this does not do**: it grants no ability to merge and none to apply. The credential
opens a proposal. [ADR-0038](0038-integration-uplift-workflows.md)'s human-as-merge-authority
constraint is untouched, and 038's FR-020 makes the platform's refusal to enact its own output
a matter of recorded provenance rather than of what a token happens to permit.

**Scope note on requester-vs-installation.** An App installation is scoped to the installing
account or organisation, not to an individual — so two requesters inside one organisation share
one installation. The credential therefore bounds the **installation**; the ownership check in
`core/authoring/request.py` bounds the **requester**, and it is the sole enforcement of that.
Stated here because a defence-in-depth claim that holds only for a single-user installation is
worse than an honest single check.
