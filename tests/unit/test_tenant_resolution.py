# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a tenant is resolved from a claim or configuration, or refused.

Every audit entry carries a tenant and the hash covers it, so a missing tenant cannot be
papered over with a literal. Inventing one would file records where nobody would look for
them, which is worse than refusing.
"""

from __future__ import annotations

import pytest

from core.identity.tenant import DEFAULT_TENANT_ENV, TenantUnresolvedError, resolve_tenant


def test_subject_claim_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DEFAULT_TENANT_ENV, "tenant-configured")
    assert resolve_tenant("tenant-from-claim") == "tenant-from-claim"


def test_falls_back_to_configuration_when_no_surface_established_a_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter and the 002-007 suites are in exactly this position."""
    monkeypatch.setenv(DEFAULT_TENANT_ENV, "tenant-configured")
    assert resolve_tenant(None) == "tenant-configured"


def test_refuses_when_nothing_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DEFAULT_TENANT_ENV, raising=False)
    with pytest.raises(TenantUnresolvedError):
        resolve_tenant(None)


def test_refuses_an_empty_configured_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set-but-blank is the shape a broken deployment produces, and it must not pass."""
    monkeypatch.setenv(DEFAULT_TENANT_ENV, "   ")
    with pytest.raises(TenantUnresolvedError):
        resolve_tenant(None)


def test_refuses_an_empty_subject_claim(monkeypatch: pytest.MonkeyPatch) -> None:
    """A present-but-empty claim must not silently fall through to the default.

    Falling back here would let a subject carrying no tenant be filed under the
    deployment's own tenant, which is precisely the boundary the claim exists to draw.
    """
    monkeypatch.setenv(DEFAULT_TENANT_ENV, "tenant-configured")
    with pytest.raises(TenantUnresolvedError):
        resolve_tenant("")
