# SPDX-License-Identifier: Apache-2.0
"""The two product-domain seams: what a user may do, and how a credential is obtained.

**Both are ours; what sits behind them is not.** A managed product's authorization system
is outside this platform's boundary and stays faked by constitutional decision — but the
interface that *asks* a product is this platform's, and until 010 it did not exist. The
distinction matters: keeping the product faked is a decision, having no way to ask one is
a gap.

The second seam exists for a less comfortable reason. `mirroring.py` used to obtain
brokered material by calling two methods the identity fabric declared "(fake only)", and
what it passed was a hard-coded fixture string:

    "HARNESS_FIXTURE_BROKERED_GRAIN_MARKER_NOT_A_REAL_SECRET"

That is production code performing a *simulated* exchange and then returning ``allow``.
The entitlement check in front of it was real and did its job, so the compensating control
was present — but a reader of that module would reasonably conclude brokering worked, and
a deployment configuring a brokered product would have had its calls permitted having
brokered nothing.

**So the fiction becomes a seam with no production implementation.** A deployment that
configures brokering and supplies no source gets a refusal naming exactly that, at the
moment it configures it. Principle IV names the brokered path's management token as the
one permitted standing credential in the whole platform; the mechanism it exists for is
ADR-0044's credential translation, which is its own feature. This is how that absence
reports itself in the meantime.
"""

from __future__ import annotations

from typing import Protocol

from core.authority.errors import ResolutionRefused


class ProductEntitlementSource(Protocol):
    """Asks a managed product what a **user** may do inside it.

    The user, never the agent. This is ADR-0044's entitlement mirroring: where a brokered
    credential is coarser than the individual, the requester's own effective entitlements
    are resolved and enforced before that credential is wielded, so an agent cannot exceed
    the person it acts for.
    """

    def entitlements_for(self, subject_user_id: str, product: str) -> frozenset[str]:
        """Return the user's effective actions in this product.

        An empty set means "this user may do nothing here" and is a legitimate answer.
        **Not being able to ask is not an empty set** — implementations raise
        :class:`~core.authority.errors.ResolutionRefused` with ``entitlement_unavailable``
        rather than returning empty, because unknown treated as empty is a denial nobody
        decided and unknown treated as full is a catastrophe.
        """
        ...


class BrokeredMaterialSource(Protocol):
    """Obtains a shared-grain credential for a product that cannot federate.

    **No production implementation exists**, deliberately. ADR-0044's rule is federate
    where the product can validate external identity and broker only where it cannot, and
    building the brokering half is that ADR's own feature. Until then a deployment that
    configures brokering has nothing to supply here, and
    :func:`require_brokered_material` turns that absence into a refusal instead of a
    permit.
    """

    def material_for(self, credential_id: str) -> str:
        """Return brokered material for this run's credential, or raise."""
        ...


def require_brokered_material(source: BrokeredMaterialSource | None, credential_id: str) -> str:
    """Obtain brokered material, or refuse because the mechanism does not exist.

    ``None`` is the production case today and refusing is the whole point: the alternative
    that shipped for three features was a placeholder string and an ``allow``, which reads
    as working and is not.

    Note where this sits — *after* the entitlement check, never before. A call the user is
    not entitled to make must be denied for **that** reason, because that is a decision the
    platform actually made about a person's permissions. Refusing it for a missing broker
    would report a platform gap where there was a policy answer, and send whoever reads the
    trail looking at our roadmap instead of at their access.
    """
    if source is None:
        raise ResolutionRefused(
            "this product requires a brokered credential and no broker is configured; "
            "credential translation (ADR-0044) is not implemented, so the call is refused "
            "rather than permitted against material that was never obtained",
            reason_code="broker_not_implemented",
        )
    return source.material_for(credential_id)


__all__ = [
    "BrokeredMaterialSource",
    "ProductEntitlementSource",
    "require_brokered_material",
]
