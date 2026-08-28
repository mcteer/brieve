# SPDX-License-Identifier: Apache-2.0
"""V6, V7, V20 — the protected set cannot drift, and the grant cannot attach (042, T003).

**FR-006 says the set is derived, never a hand-maintained list.** Terraform cannot reflect
over its own resources, so the derivation is split in two: `scratch.tf` writes the list, and
this file makes the completeness mechanical. The list is hand-written; *that it is complete*
is a merge gate.

That split is the same honesty shape as 040's capability inventory — **built and unlisted**
fails a merge instead of being found by accident, which is how `run_program` and 038's
authoring trio both shipped unreachable.

**The runtime alternative was measured and rejected** (research R4): "every live policy minus
the scratch namespace" reads as more automatic and is wrong here, because in this enclave
every live policy IS a trust-fabric policy — the derivation would protect everything, US1
could read nothing, and the safety rows would pass by making the feature unusable.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "infra" / "modules" / "trust-fabric"
SCRATCH = MODULE / "scratch.tf"

#: The reserved measurement namespace. Nothing the trust fabric declares may occupy it.
SCRATCH_PREFIX = "scratch-agent-"

#: Vault paths that ATTACH a policy to something. The impact check must never be able to
#: reach one — a scratch policy attached to an entity is no longer scratch, it is a grant.
ATTACH_PATH_MARKERS = ("identity/", "auth/token/roles/", "/role/")


def _declared_policies() -> dict[str, str]:
    """Every `resource "vault_policy"` in the module, mapped to its declared `name`."""
    declared: dict[str, str] = {}
    for source in sorted(MODULE.glob("*.tf")):
        text = source.read_text()
        for match in re.finditer(r'resource\s+"vault_policy"\s+"(\w+)"\s*\{', text):
            block = text[match.end() : match.end() + 2000]
            name = re.search(r'^\s*name\s*=\s*"([^"]+)"', block, re.M)
            declared[match.group(1)] = name.group(1) if name else ""
    return declared


def _published_block() -> str:
    """The `names = sort(concat(...))` expression `scratch.tf` publishes."""
    text = SCRATCH.read_text()
    start = text.index("names = sort(concat(")
    return text[start : text.index("\n  })", start)]


def test_v6_every_declared_policy_appears_in_the_published_protected_set() -> None:
    """V6 — the row that keeps FR-006's "derived" honest.

    A policy added to the trust fabric and not added here would be a policy an authoring run
    could rewrite. This fails the merge that adds it, at the moment the name is written,
    rather than at the moment somebody exploits it.
    """
    published = _published_block()
    missing = [
        resource for resource in _declared_policies() if f"vault_policy.{resource}" not in published
    ]

    assert not missing, (
        f"{missing} are declared in infra/modules/trust-fabric/ and absent from the "
        f"protected set published by scratch.tf. A trust-fabric policy outside that set is "
        f"one a policy-authoring run may rewrite — which is the escalation Principle IV "
        f"makes structurally unavailable. Add it to `names`, do not remove this row."
    )


def test_v6_the_gated_policies_are_referenced_in_a_form_that_survives_their_gating() -> None:
    """The subtlety that made `terraform validate` refuse to plan, pinned so it stays fixed.

    Two policies are not singular resources: `agent_ceiling` is `for_each` over the agent
    definitions (**N ceilings, one per definition** — the most important names in the set),
    and `authority_change` is `count`-gated on control groups. Referencing either with a
    plain `.name` fails outright, and the tempting repair is to drop them from the list —
    which would publish a protected set silently missing every ceiling.
    """
    published = _published_block()

    assert "values(vault_policy.agent_ceiling)[*].name" in published, (
        "agent_ceiling is for_each over agent definitions; a singular reference cannot "
        "plan, and omitting it would leave every definition's ceiling unprotected"
    )
    assert "vault_policy.authority_change[*].name" in published, (
        "authority_change is count-gated; the splat publishes it when it exists and "
        "nothing when it does not, which describes the applied estate"
    )


def test_v7_no_trust_fabric_policy_occupies_the_measurement_namespace() -> None:
    """V7 — FR-020's reserved namespace, as a merge gate rather than a convention.

    The impact check's entire product-level bound is that `scratch-agent-*` contains nothing
    but throwaway measurements. A trust-fabric policy named into that prefix would be
    writable and deletable by every dispatched run, and the `allowed_policies_glob` that
    looks like the safety argument would be handing out the real thing.
    """
    trespassing = {
        resource: name
        for resource, name in _declared_policies().items()
        if name.startswith(SCRATCH_PREFIX)
    }

    assert not trespassing, (
        f"{trespassing} occupy the reserved measurement namespace {SCRATCH_PREFIX!r}. Every "
        f"dispatched run may create, overwrite and delete anything with that prefix, so a "
        f"trust-fabric policy there is granted away rather than protected."
    )


def test_v20_the_scratch_grant_cannot_attach_a_policy_to_anything() -> None:
    """V20 — SC-011 rests on a scanned grant, not on the handler happening not to try.

    FR-021 says a scratch policy is never attached to any entity, role, or auth mount. The
    structural argument is that the impact sequence has no attach step — true, and only true
    of the code as written today. This asserts the stronger property: the grant **cannot
    express** attachment, so an edit adding one fails here rather than quietly turning a
    throwaway measurement into a standing grant.

    `auth/token/create/scratch-check` is exempt and is the reason this scans for
    `auth/token/roles/` specifically: minting a token through a role is how the measurement
    gets its subject, while writing a token *role* would be redefining what may be minted.
    """
    text = SCRATCH.read_text()
    start = text.index('resource "vault_policy" "scratch_policy_check"')
    grant = text[start : text.index("\n}", start)]

    granted_paths = re.findall(r'^\s*path\s+"([^"]+)"\s*\{', grant, re.M)
    attaching = [
        path
        for path in granted_paths
        if any(marker in path for marker in ATTACH_PATH_MARKERS)
        and not path.startswith("auth/token/create/")
    ]

    assert not attaching, (
        f"the scratch grant reaches {attaching}, which can attach a policy to a principal. "
        f"SC-011 says zero scratch policies are ever attached to an entity, role, or auth "
        f"mount — a measurement that can be attached is a grant, and it would outlive the "
        f"check that created it."
    )


def test_v20_the_scratch_grant_stays_inside_the_measurement_namespace() -> None:
    """The other half: every policy path in the grant is `scratch-agent-*`.

    Without this, V20 would pass a grant that added `sys/policies/acl/*` — no attach path,
    total authority over every policy in the estate.
    """
    text = SCRATCH.read_text()
    start = text.index('resource "vault_policy" "scratch_policy_check"')
    grant = text[start : text.index("\n}", start)]

    policy_paths = [
        path
        for path in re.findall(r'^\s*path\s+"([^"]+)"\s*\{', grant, re.M)
        if path.startswith("sys/policies/acl")
    ]

    assert policy_paths, "the grant names no policy path at all; the scan is not reading it"
    assert all(path.startswith(f"sys/policies/acl/{SCRATCH_PREFIX}") for path in policy_paths), (
        f"{policy_paths} reaches outside the measurement namespace — the product-level "
        f"bound is the one layer that survives a platform bug, and this is where it is set"
    )


def test_the_sweep_grant_is_not_held_by_a_dispatched_run() -> None:
    """`list` over every policy name belongs to the long-lived service, never to a run.

    Finding an orphan means finding a name nobody told you about, so the sweep genuinely
    needs enumeration — which is exactly why a dispatched run must not have it.
    """
    auth = (MODULE / "auth.tf").read_text()
    # Located by regex rather than by an exact-width slice. `terraform fmt` aligns `=` within
    # contiguous runs of attributes, so ANY comment added inside the block re-aligns the
    # others — 054 added one and this row failed on the whitespace while the property it
    # asserts was untouched. The property is worth keeping; the brittleness was not.
    anchor = re.search(r'^\s*role_name\s*=\s*"agent-run"', auth, re.MULTILINE)
    assert anchor is not None, "the agent-run JWT role is gone from auth.tf"
    agent_role = auth[anchor.start() :]
    agent_role = agent_role[: agent_role.index("\n}")]

    assert "scratch_sweep" not in agent_role, (
        "the sweep grant enumerates every policy in the estate; on a dispatched run that is "
        "reconnaissance, and the run has no use for it — it knows its own scratch names"
    )
    assert "scratch_policy_check" in agent_role, (
        "the run must carry the measurement grant, or the impact check refuses for want of "
        "authority and the feature has no instrument"
    )
