# Hooks

**Reserved extension point — still empty, and the README is what changed.** This directory
was scaffolded in 001 for custom pre/post-tool-use enforcement hooks, back when "enforcement
behavior is a later feature."

That feature was built, and it lives in the sealed core, not here: `src/core/hooks/` holds
the hook engine every `invoke_tool` call passes through — authority (ceiling + live policy,
fail-closed), entitlement mirroring, and suspension — installed outermost on the governed
agent so nothing downstream can produce an ungoverned execution.

What stays reserved here is the *operator-authored* half: hooks a deployment supplies beside
the platform's own. Nothing loads from this directory today, and adding that loader is a
feature with its own security review — a drop-in enforcement path done casually is also a
drop-in bypass path. ADR-0014's wire-level guardrail is the adjacent, also-unbuilt second
layer.
