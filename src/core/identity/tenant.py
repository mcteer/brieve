# SPDX-License-Identifier: Apache-2.0
"""Tenant resolution.

Every audit entry carries a tenant, because the evidence read path is tenant-bounded and
the bounding dimension has to be inside the hash chain (FR-010d). That makes the field
required on entries written by runs no surface ever touched: ``start_governed_run`` is
reached from the primary adapter and from the 002–007 suites, none of which has an
identity provider to read a claim from.

So there are two sources, in order:

1. The authenticated subject's tenant claim, where a surface established one.
2. ``HARNESS_DEFAULT_TENANT`` from the environment.

**Absent means refuse**, not a literal fallback. A subject with no tenant is refused for
the same reason (a default tenant chosen by accident is still a tenant), and silently
writing records under an invented value would put them somewhere nobody would think to
look for them.

One tenant is configured today, so in practice both paths yield the same value — which is
the point. The dimension is enforced everywhere from the first commit, so multi-tenancy
later changes what populates it rather than adding a field the existing records lack.

Reading ``os.environ`` directly follows :mod:`core.durability.credentials`, which is
core's only precedent for configuration. If core ever grows a settings seam, this is one
of the two places that should move onto it.
"""

from __future__ import annotations

import os

from core.errors import CoreError

DEFAULT_TENANT_ENV = "HARNESS_DEFAULT_TENANT"


class TenantUnresolvedError(CoreError):
    """No tenant could be resolved. Fail closed rather than invent one."""


def resolve_tenant(subject_tenant_id: str | None = None) -> str:
    """Return the tenant for this context, or refuse.

    ``subject_tenant_id`` is the claim a surface established, when there was a surface.
    """
    if subject_tenant_id is not None:
        stripped = subject_tenant_id.strip()
        if not stripped:
            raise TenantUnresolvedError(
                "subject tenant claim is present but empty; refusing rather than defaulting"
            )
        return stripped

    configured = os.environ.get(DEFAULT_TENANT_ENV, "").strip()
    if not configured:
        raise TenantUnresolvedError(
            f"no subject tenant claim and {DEFAULT_TENANT_ENV} is unset; "
            "every audit entry must carry a tenant, and inventing one would file records "
            "where nobody would look for them"
        )
    return configured


__all__ = ["DEFAULT_TENANT_ENV", "TenantUnresolvedError", "resolve_tenant"]
