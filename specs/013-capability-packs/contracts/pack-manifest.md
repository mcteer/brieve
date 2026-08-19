# Contract: The Pack Manifest and What Loading Does

**Feature**: `specs/013-capability-packs` | **Date**: 2026-07-29 | **Status**: Planned

A pack **declares**; the platform **decides**. Nothing in a manifest grants anything.

---

## Loading, in order

1. **Read the manifest.** A malformed manifest refuses the load; it does not partially load.
2. **Verify every content digest.** Skills first, then `AgentPin` rows (049). A mismatch
   refuses with `digest_mismatch` and names the file. A missing or empty phase `AGENTS.md`
   refuses `agents_missing` / `agents_empty`. Verification happens at load rather than at
   review, because review is when someone looked and load is when it matters.
3. **Validate every tool and hook declaration.** A pack hook declaring `capability_kind = governance` refuses `governance_hook_from_pack` — enforcement is the platform's. A non-repeatable tool with no observer refuses
   `observer_required`; a `product_mode` other than `none` without `product` and
   `product_action` refuses `incomplete_product_binding`. Both in the pack's own vocabulary
   rather than as a registry `ValueError` one layer down.
4. **Check the eval-coverage floor.** A pack shipping fewer than five cases per suite is
   refused `insufficient_eval_coverage` — **at load, not at gate time**. The failure belongs
   where the pack is added rather than where a gate later reports a number nobody reads.
   Authoring packs additionally require five `[[agents]]` covering every `PhaseName`
   (`agents_incomplete`) and a non-empty sibling `PROVENANCE.md` per phase
   (`agents_provenance_missing`).
5. **Register the tools** into the one governed registry, `risk_class` preserved.
6. **Record the pack as available**, not as *granted* — availability is not access.

**All manifest validation happens at load.** A refusal added later belongs in this sequence
rather than beside it — the point of one ordered list is that a reader knows where to look
for every way a pack can be rejected. **049 amends this list** (it is no longer closed):
see `specs/049-phase-product-prompts/contracts/pack-agents.md`. After skill digest
verification, an authoring pack (workflow name contains `"author"`) must declare five
`[[agents]]` covering every phase (`agents_incomplete`); each `AgentPin` digest is
verified (`digest_mismatch` / `agents_missing` / `agents_empty`); sibling
`agents/<phase>/PROVENANCE.md` must be present and non-empty (`agents_provenance_missing`).

## What loading does NOT do

- **It does not execute anything from the pack.** A tool declaration names a handler; the
  handler is resolved from what the platform already provides. A manifest that could supply
  executable code would be a way to run arbitrary code by shipping a file, and no amount of
  review downstream would fix that.
- **It does not widen a ceiling.** A pack declaring `apply` does not give a definition
  `apply`. The ceiling still decides, and a declaration outside it refuses
  `pack_exceeds_ceiling` (FR-005) — asserted, because "the pack said so" is the obvious
  shortcut and would read as a feature rather than a hole.
- **It does not let a pack author enforcement.** Pack hooks register at non-governance kinds only, so a pack cannot satisfy the platform's enforcement-is-whole check with its own hook, and `GovernanceCapability` still runs first.
- **It does not bypass hooks.** Pack tools are `ToolRegistry` registrations, so they inherit
  the pipeline **by construction**. There is no pack-tool code path; that is the whole
  design (FR-003).

## Isolation between packs

A definition reaches only the packs it names. Two packs load side by side and neither is
reachable from a definition that does not name it (SC-012).

**Same-tool-name collision** (the spec's edge case): a tool name is qualified by its pack,
so `terraform.plan` and `vault.plan` are different tools. An unqualified name in a
definition that reaches two packs declaring it is **refused as ambiguous**, not resolved by
precedence. Precedence would make the answer depend on load order, and load order is the
kind of thing that changes without anyone deciding it did.

## Risk class

`read | write | destructive | secret_touching`. Declared per tool, preserved into the
registry, and available to approval and plan-gating.

**This is new.** The glossary has defined it since the beginning; nothing in the code has
ever carried it. Registry review MAY require process isolation (MCP) for `secret_touching`
and `destructive` — Principle II's provision, which needs a risk class to act on and has
therefore never been actionable.

## Provenance

| `provenance` | Requires | Promotion checks |
| --- | --- | --- |
| `adopted` | `upstream` table: repository, commit, licence | Pinned commit exists; content hashes to what was recorded; injection lens; evals |
| `authored` | Nothing extra | Injection lens; evals — and FR-027d's format obligation |

**The two packs are deliberately one of each.** Terraform adopts from
[`hashicorp/agent-skills`](https://github.com/hashicorp/agent-skills) (MPL-2.0), giving
ADR-0004's supply chain a genuine subject: a real upstream, a real commit to pin, real
content to review. Vault authors, because upstream lists Vault as a future product — and
authors *in the upstream format*, so the pack becomes `adopted` by changing a provenance
record rather than by rewriting content (FR-027d).

## What a passing load does not prove

Terraform's **tools** are fixture-backed: Terraform is not deployed in the enclave, so that
pack's tool layer is exercised against doubles. The tool half is what Principle II governs,
and a pack whose tools were never called must not read as one whose tools were. Recorded
here and in the conformance contract rather than left to inference.
