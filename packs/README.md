# Capability packs

A **capability pack** is the unit of product knowledge: a manifest of tools (each with a
risk class), skills, pack hooks, workflows, and evals, for one managed product.

This directory was reserved as an extension point before there was anything to put in it.
013 is the feature that fills it.

**New products are new packs; the core does not change.** That is Principle I holding at
the content layer, and it is asserted rather than claimed — `tests/conformance/packs/`
contains a row that greps `src/core` for any product name, and a second that runs
`git diff --stat` against the commit adding the *second* pack and requires it empty under
`src/core`.

## Why this directory is at the repository root

Not under `src/`, deliberately.

**A pack is content, not code.** Putting `packs/terraform` inside the Python package tree
would ship Terraform knowledge in the distribution whose entire claim is that it has none.
The core is product-blind; a distribution carrying product knowledge is product-blind only
in the sense that it does not *read* it, which is a much weaker property and not the one
Principle I states.

It also makes the check trivially inspectable. "Does anything under `src/core` mention
terraform or vault" is a question with a mechanical answer as long as the content lives
somewhere `src/core` is not.

## What a pack contains

```text
packs/<name>/
├── pack.toml     # The manifest: tools, skills, hooks, workflows, evals, probe
├── skills/       # Adopted (with PROVENANCE.md) or authored, in the Agent Skills format
└── evals/        # Cases for each suite this pack ships
```

**A manifest is data, never code.** Loading executes nothing from a pack. A tool
declaration *names* a handler and the handler is resolved from what the platform already
provides — the same rule applies to the pack's `probe`, because the health checker is the
single owner of "reachable" and a pack supplying its own would be pack code deciding
whether its own product is up.

## The two packs, and why there are two

| Pack | Provenance | What it proves |
| --- | --- | --- |
| `terraform` | **adopted** from [`hashicorp/agent-skills`](https://github.com/hashicorp/agent-skills) at a pinned commit, MPL-2.0 | ADR-0004's supply chain against a real upstream — genuine provenance to check, a real version to pin, real content to run an injection-lens review over |
| `vault` | **authored** here, in the upstream format | Invocation. Vault runs in the enclave, so this is the pack whose *tools* reach a product that actually answers |

One pack would have proved neither: with a single pack there is nothing to be independent
*of*. Two authored packs would have built the supply chain and never tested it.

**Terraform's tool layer is fixture-backed**, because Terraform is not deployed in the
enclave. The tool half is what Principle II governs, so a pack whose tools were never
called must not read as one whose tools were — `contracts/conformance-packs.md` records it,
and a row asserts that a pack's eval status and its tool reachability stay separate facts.

**The authored Vault skills use the upstream format on purpose.** They are intended for
contribution back to `hashicorp/agent-skills`, so authoring here is a temporary state by
design rather than a permanent fork — ADR-0004 says adopt what upstream ships and migrate
onto it as it matures, and a divergent shape would make that migration a rewrite.
