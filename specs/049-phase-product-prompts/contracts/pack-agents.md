# Contract: Pack phase `AGENTS.md` files

**Feature**: `specs/049-phase-product-prompts` | **Date**: 2026-08-19

Named paths bind exactly. Substitutes are bugs.

## Layout

```text
packs/<pack>/agents/<phase>/AGENTS.md
packs/<pack>/agents/<phase>/PROVENANCE.md
```

`<phase>` ∈ {`research`, `plan`, `write`, `judge`, `propose`} (`core.authoring.progress.PhaseName`).

v1 packs: `terraform`, `vault`. Further products are new packs with the same five paths
(FR-005). Core does not gain product identifiers.

## Manifest

```toml
[[agents]]
phase = "research"
path = "agents/research/AGENTS.md"
version = "0.1.0"
digest = "<sha256 hex of AGENTS.md>"
```

Five rows on every pack that declares an authoring workflow. The table is a pin, not the
instruction text.

## Loader sequence (amends 013 pack-manifest "closed list")

After digest verification of skills, for an authoring pack:

1. Require five `[[agents]]` covering every `PhaseName` (`agents_incomplete`).
2. Verify each `AGENTS.md` digest (`digest_mismatch` / missing file).
3. Refuse empty `AGENTS.md` (`agents_empty`).
4. Require sibling `PROVENANCE.md` non-empty (`agents_provenance_missing`).

Loading still executes nothing from the pack.

## Resolution helper (named)

`core.packs.agents.load_phase_agents(pack_name: str, phase: PhaseName, *, loader, packs_root) -> PhaseAgents`

- Does not import or mention managed product identifiers.
- Does not read repository-root `AGENTS.md`.
- Does not read `SKILL.md` or `pack.toml` prose as the body.
- Raises `ManifestError` / typed refusal with the reason codes above.

## Bind helper (named)

`bind_phase_agents(run, phase) -> PhaseAgents` in dispatch (surfaces):

- Pack set must be size 1 (`pack_unbound` / `pack_ambiguous`).
- Calls `load_phase_agents`.
- Writes `{pack}/agents/{phase}` into `content_pins`.
- Returns the body for `ChoiceRequest.instruction`.

Failure marks the 047 phase failed and does not call `open_proposal`.

## Isolation

A run bound to pack A never loads pack B's `agents/` files. Asserted as a property (SC-002),
not a demo.
