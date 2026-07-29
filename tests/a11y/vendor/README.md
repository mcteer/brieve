# Vendored: axe-core

**File**: `axe.min.js`
**Version**: 4.10.2
**Source**: https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js
**SHA-256**: `b511cd9dec01c76f4b2ad1723b66b6db37d4c2eb4ed199076e1829d9ee7b75e3`
**License**: Mozilla Public License 2.0 — Copyright (c) 2015–2024 Deque Systems, Inc.
**Modifications**: none. Byte-for-byte as published.

## Why vendored rather than fetched

**What the gate executes is pinned** (Principle VIII). A ruleset fetched at test time
would make the accessibility gate's *meaning* a function of when it ran — a page passing
on Tuesday and failing on Wednesday with no change to the page is a gate nobody can act
on, and a page that silently stops being checked because a new version dropped a rule is
worse. The digest above is what makes "pinned" checkable rather than asserted.

It also keeps the a11y lane runnable without network egress, which every other lane in
this repository already assumes.

## Upgrading

Deliberate, never automatic:

1. Download the new version, record its digest here, replace the file.
2. Run `make a11y` and read the **diff in findings**, not just the exit status — a new
   version finding more is the point; a new version finding *less* means a rule went away
   and the manual checklist in
   `specs/012-conversational-portal/contracts/conformance-portal.md` may need to grow.
3. Note the version bump in the commit message with what changed in the finding set.

## What this ruleset does not cover

Axe asserts a subset of WCAG 2.2 AA — the machine-checkable part. The criteria it cannot
assert are enumerated in
[`conformance-portal.md`](../../../specs/012-conversational-portal/contracts/conformance-portal.md),
with a named human runner. A green run here is not a conformance claim.
