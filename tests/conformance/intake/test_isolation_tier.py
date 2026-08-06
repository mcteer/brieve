# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the tier is a tier, not a ceiling (A0, FR-006/FR-009).

**This row exists because the first task list built a ceiling and called it containment.** A
ceiling bounds what a definition may *call*; a tier bounds what the process can *reach*. An
analysis agent with the narrowest ceiling in the fleet, in an allocation sharing the host
network and mounting the repository, passes every ceiling assertion while sitting one library
call away from everything the ceiling was protecting.

So the posture is asserted **structurally, from the jobspec**, and the enforcement is asserted
**by clause** — a tier that failed opaquely would be one operators route around.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from core.isolation.tier import IsolationTier, TierPosture, TierRefused, assert_tier

REPO = pathlib.Path(__file__).resolve().parents[3]
JOBSPEC = REPO / "infra" / "jobs" / "analysis-tier.nomad.hcl"


def _jobspec() -> str:
    return JOBSPEC.read_text()


def test_the_check_covers_something() -> None:
    """Without this, a moved or empty jobspec makes every assertion below vacuous."""
    assert JOBSPEC.exists(), "the hardened tier's jobspec is missing"
    body = _jobspec()
    assert len(body) > 500
    assert 'job "analysis-tier"' in body


def test_the_tier_does_not_share_the_host_network() -> None:
    """The single most important line: bridge, never host."""
    body = _jobspec()
    assert re.search(r'mode\s*=\s*"bridge"', body), "the network block is not bridge mode"
    assert re.search(r'network_mode\s*=\s*"bridge"', body), "the task is not bridge mode"
    assert not re.search(r'network_mode\s*=\s*"host"', body), (
        "the analysis tier shares the machine's network namespace — a workload reading "
        "hostile content would sit beside every other allocation"
    )


def test_the_tier_mounts_no_repository() -> None:
    """The delta arrives as payload; nothing else is on disk.

    Asserted as the absence of a `mount` block rather than by reading prose about one — the
    file explains at length WHY there is no mount, and a text search for "mount" would match
    that explanation and pass while a real mount sat beside it.
    """
    body = _jobspec()
    mount_blocks = re.findall(r"^\s*mount\s*\{", body, re.M)
    assert mount_blocks == [], (
        f"the analysis tier mounts something ({len(mount_blocks)} mount blocks); the delta "
        "must be delivered as input so a redirected analyzer has nothing to read or write"
    )


def test_the_tier_declares_an_egress_allowlist() -> None:
    body = _jobspec()
    assert "HARNESS_EGRESS_ALLOWLIST" in body, "no egress allowlist is declared"


def test_a_definition_requiring_the_tier_is_refused_outside_one() -> None:
    """Enforcement, by clause. A tier nothing checks is a comment in a jobspec."""
    hardened = TierPosture("bridge", frozenset({"github.com"}), repo_mounted=False)
    assert_tier(IsolationTier.HARDENED, hardened)  # does not raise

    with pytest.raises(TierRefused, match="not 'bridge'"):
        assert_tier(IsolationTier.HARDENED, TierPosture("host", frozenset(), False))

    with pytest.raises(TierRefused, match="repository is mounted"):
        assert_tier(IsolationTier.HARDENED, TierPosture("bridge", frozenset(), True))


def test_a_standard_definition_is_unaffected() -> None:
    """The tier is opt-in. Every existing definition keeps running as it does today."""
    assert_tier(IsolationTier.STANDARD, TierPosture("host", frozenset(), repo_mounted=True))
