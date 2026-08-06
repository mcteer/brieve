# SPDX-License-Identifier: Apache-2.0
"""Where a definition's work is permitted to run.

**Here rather than in `core.intake`, and the move is the point.** 037 built the hardened
untrusted-content tier and put it inside the package that was its only consumer. 038 is the
second, and it is not part of the supply chain — so `core.authoring` importing `core.intake`
would encode a dependency that is false and would eventually be relied upon.

A tier is not a ceiling. A ceiling bounds what a definition may **call**; a tier bounds what
the process can **reach**. Conflating them was 037's first CRITICAL, and the distinction is
written into `tier.py` so it cannot be re-conflated.
"""

from core.isolation.tier import (
    IsolationTier,
    SubjectMount,
    TierPosture,
    TierRefused,
    assert_tier,
)

__all__ = [
    "IsolationTier",
    "SubjectMount",
    "TierPosture",
    "TierRefused",
    "assert_tier",
]
