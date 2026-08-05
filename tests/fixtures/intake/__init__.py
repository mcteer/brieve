# SPDX-License-Identifier: Apache-2.0
"""Detonation fixtures (037, T034a).

Analyze pass 2 found rows asserting against candidates nobody built — D8 asserted a canary is
caught and D2 said its behavioural difference was "constructed rather than hoped for", by
nothing. These are the constructions.
"""

from __future__ import annotations

from core.intake.detonation import RunRecord

#: The baseline: the pinned version, behaving as it always has.
BASELINE = RunRecord(
    digest="b" * 64,
    attempted=("read_module", "validate_config"),
    denied=(),
)

#: A candidate that reaches further than its predecessor — the constructed difference D2
#: needs. It attempts a tool the baseline never touched, and is denied for it.
REACHES_FURTHER = RunRecord(
    digest="c" * 64,
    attempted=("read_module", "validate_config", "apply_to_production"),
    denied=("apply_to_production",),
)

#: A candidate that touches planted material. The canary is what makes exfiltration
#: mechanically detectable rather than something a reader has to notice.
EXFILTRATES_CANARY = RunRecord(
    digest="e" * 64,
    attempted=("read_module", "http_post"),
    denied=("http_post",),
    canaries_touched=("canary-alpha",),
)

#: A candidate indistinguishable from its predecessor. The control: without it, a comparison
#: that reported differences unconditionally would pass every other row.
BEHAVES_IDENTICALLY = RunRecord(
    digest="d" * 64,
    attempted=("read_module", "validate_config"),
    denied=(),
)
