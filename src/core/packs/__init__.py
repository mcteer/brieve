# SPDX-License-Identifier: Apache-2.0
"""Capability packs — the seam through which product knowledge enters a product-blind core.

**Nothing in this package names a product.** That is the whole claim, and it is asserted
structurally rather than reviewed: `tests/conformance/packs/test_core_is_product_blind.py`
greps `src/core` for any product name and separately requires that the commit adding the
*second* pack changed no file under `src/core`. Content lives in `packs/` at the repository
root, deliberately outside the Python package tree, so shipping the distribution does not
ship Terraform.

**A manifest declares; the platform decides.** Loading executes nothing from a pack. A tool
declaration *names* a handler and the handler is resolved from what the platform already
provides; a pack's `probe` works the same way, because the health checker is the single
owner of "reachable" and a pack deciding whether its own product is up would be exactly the
second opinion FR-006a exists to prevent. There is no code path here that imports, execs,
or evaluates anything a pack ships.

The three things that make that boundary hold rather than merely describe it:

**Pack tools are ordinary registry registrations.** They inherit the hook pipeline by
construction, not by discipline — there is no pack-tool code path to bypass, which is why
the no-bypass row can be asserted structurally.

**A pack cannot widen a ceiling.** A pack declaring tools its definition's ceiling omits is
the obvious shortcut and would read as the pack system working. It refuses.

**A pack cannot register governance.** `has_required_governance_hooks` identifies the
platform's own enforcement by `capability_kind == GOVERNANCE`, so a pack able to register at
that kind could satisfy the enforcement-is-whole check with its own hook — enforcement
authored by whoever ships a pack. Refused at load.
"""
