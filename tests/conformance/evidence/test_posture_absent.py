# SPDX-License-Identifier: Apache-2.0
"""What an unconfigured estate says, and where this configured one ships (015, SC-006).

Two rows about the boundaries of the claim rather than the mechanism.

**ABSENT is a posture, not an error.** An estate with no second copy has no
tamper-evidence, and the platform states that plainly. The failure mode being guarded
against is a default that reads as protected — a posture field left at something reassuring
because nothing set it otherwise is worse than no field, since it converts an absence of
information into a false assurance.

**The destination is NEAR.** ADR-0055 adds an organization-operated collector and does not
open a far one; ADR-0020's default for third-party and hosted destinations is unchanged.
That is what makes the air-gapped tier work by construction rather than by exception: the
connectivity tier changes WHERE the destination is, never WHETHER there is one, and this
whole suite runs against a collector on the local network — which is the air-gapped
scenario, not a stand-in for it.
"""

from __future__ import annotations

import ipaddress
from typing import Any

import pytest

from core.audit.reconcile import posture_reason, reconcile

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


def test_row_an_estate_with_no_destination_reports_absent(
    platform_admin_connection: Any,
) -> None:
    """SC-006 / FR-009 — stated, not defaulted.

    An estate with no second copy has no tamper-evidence. Saying so plainly is better than a
    substitution that quietly is not one — and better than a posture field that happens to
    read as protected because nothing set it otherwise.
    """
    report = reconcile(local=platform_admin_connection, destination=None)

    assert report.posture == "absent"
    assert report.destination_verified == "unverified"
    assert "no destination is configured" in posture_reason(report), (
        "the ABSENT posture arrived without saying what is absent"
    )


def test_row_this_estate_ships_within_its_own_boundary_and_not_beyond_it(
    egress_configured: dict[str, Any],
) -> None:
    """ADR-0020's default is unchanged — this adds a near destination, not a far one.

    Asserted against the configuration the suite actually runs with, because "we would
    never point this at a hosted service" is the kind of claim that stays true until the
    first convenient exception. A destination outside the local network here would mean
    every other row in this lane had been demonstrating export, not egress.
    """
    host = str(egress_configured["host"])
    address = ipaddress.ip_address(host)

    assert address.is_loopback or address.is_private, (
        f"the audit destination is {host}, which is not within the organization's own "
        "network — ADR-0055 adds a NEAR destination and leaves ADR-0020's default for "
        "third-party and hosted destinations exactly where it was"
    )
