# ADR-0066: Version control is reached through adopted CLIs, not an MCP server

- **Status**: Accepted
- **Date**: 2026-08-07
- **Relates to**: [ADR-0064](0064-version-control-is-a-platform-capability.md) (what the capability *is*; this records how it is *reached*), [ADR-0038](0038-integration-uplift-workflows.md), [ADR-0062](0062-authoring-credentials-are-vended-per-task.md), [ADR-0001](0001-framework-agnostic-core.md)
- **Requirements**: R5, R11, R12

## Context

Principle II governs transport per tool: **MCP** where a server exists, is mature, and is
supported — *"a determination made at registry review and revisited each semester"* — and
**native** otherwise, with the explicit rider that *"authoring an MCP server is never required
merely for protocol uniformity."*

041 makes 038's authoring tier reachable, which means `open_proposal` needs its first
production handler. An official GitHub MCP server exists and is maintained by the vendor, so
Principle I's adopt-what-vendors-ship rule and Principle II's MCP clause both point at it. That
was the initial determination in this feature's planning, and it was **reversed on
measurement**.

## Decision

**The version-control capability is reached through adopted vendor CLIs**: `git` for clone and
push, `gh` for opening the proposal. No MCP server is introduced.

The determination is recorded here because Principle II makes MCP-versus-native a *decision*
rather than a default, and a decision made silently is what that clause exists to prevent.

## Why the MCP server was rejected

**The external surface is three operations.** One clone, one push, one pull request. Against
that, the server is a process with its own supply chain, its own release cadence, and its own
auth model.

**It would run inside the hardened tier.** ADR-0038's tier exists to process *untrusted
repository content* — a customer's private codebase, mounted read-only, analysed by a model.
The publishing task is the one holding the credential. Adding a long-running server process to
that task widens the attack surface of the exact place this architecture works hardest to keep
narrow, and does so to make one API call.

**Its tool surface is wildly wider than the task's scope.** The server exposes issues, actions,
file contents, search, releases. The proposer task's entire declared scope is
`RUN_REQUESTED_TOOLS = "open_proposal"`. Adopting the server means constraining nearly all of
it back off — and a capability surface you must remember to keep constrained is the shape
Principle II's one-registry rule is written against.

**It would owe a Principle VI trigger.** *"Every additional operated component REQUIRES a named
trigger recorded in an ADR."* A server process is an operated component. Rejecting it does not
merely avoid a cost; it avoids owing an argument that would have been thin.

## Why core `git` alone is insufficient, and why that is a narrow gap

`git` covers cloning and pushing completely. It does **not** open a pull request: a PR is a
forge concept, not a git one. `git request-pull` — the closest core command — generates a
summary for *emailing* a maintainer, which is the kernel mailing-list workflow and not this.

So the gap between "git is enough" and "we need more" is exactly one operation. `gh pr create`
fills it, and `gh` is GitHub's own CLI: adopted, not authored, exactly as Principle I asks.

## Consequences

**Credential delivery is simpler, which is a security property and not a convenience.** `gh`
authenticates from `GH_TOKEN` in the environment. The installation token minted per ADR-0062
is passed per invocation and never written to disk — no `gh auth login` (which writes
`hosts.yml`), no token in a remote URL (which lands in `.git/config` and process listings), no
credential store. `git` reaches the same token through `gh`'s credential helper, so there is
one delivery path rather than two.

**Two binaries become pinned dependencies of the publishing task image.** They are adopted
content and are pinned and provenance-checked like any other (Principle VIII). The task
verifies presence and version at start and **fails `tooling_missing`** rather than installing
at runtime — a runtime `apt-get` inside the hardened tier would be an unpinned network fetch
into the process handling untrusted content, which the static-allowlist posture refuses.

**This is a determination, not a permanent rule.** Principle II says these are revisited each
semester. If the platform's version-control surface grows past a handful of operations — issue
triage, review comments, checks — the arithmetic changes and the server becomes the cheaper
answer. What would not change is the tier placement question: any such server belongs outside
the hardened task, and that is the harder half of this decision.

**The reversal is recorded deliberately.** MCP was chosen first, from reading Principle II's
clause as a default. It is not a default; it is a determination with a cost side. Writing down
only the conclusion would leave the next feature to make the same first pass.
