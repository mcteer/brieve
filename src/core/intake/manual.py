# SPDX-License-Identifier: Apache-2.0
"""Adoption when the gauntlet is unavailable, and the record that keeps it honest (FR-025).

**A pipeline whose absence blocks all adoption has become a dependency of the supply chain it
protects** — an availability problem presenting as a security control. Worse, it pushes an
operator under deadline toward editing the pin directly, which leaves no record at all.

So the manual path stays. What makes it safe is not that it is hard but that it is *visible*:
using it writes a record naming who, when, which skill and why. A bypass that is recorded can
be reviewed for becoming routine; a bypass that is forbidden becomes invisible.

**And it must be no quieter than a gauntlet promotion.** The failure being guarded against is
not the bypass existing — it is the bypass being easier to reach for than to notice.
"""

from __future__ import annotations

from core.audit.schema import AuditEventType
from core.errors import CoreError
from core.run import GovernedRun


class BypassRefused(CoreError):
    """The manual path was taken without saying who took it, or why."""


def record_bypass(
    run: GovernedRun,
    *,
    skill_name: str,
    to_version: str,
    subject_user_id: str,
    reason: str,
) -> None:
    """Record that a skill was adopted without the gauntlet.

    Both attributions are required and neither has a default. ``subject_user_id`` because a
    bypass with no name is an unattributable act; ``reason`` because a bypass nobody has to
    justify is the normal route by the second time it is taken.
    """
    if not subject_user_id.strip():
        raise BypassRefused(
            "the manual path requires a subject: a bypass with no name is an act nobody "
            "can be asked about"
        )
    if not reason.strip():
        raise BypassRefused(
            "the manual path requires a reason: a bypass nobody has to justify is the "
            "normal route by the second time it is taken"
        )

    run.audit_sink.append_event(
        correlation_id=run.correlation_id,
        tenant_id=run.tenant_id,
        event_type=AuditEventType.INTAKE_BYPASSED,
        payload={
            "skill_name": skill_name,
            "to_version": to_version,
            "subject_user_id": subject_user_id,
            "reason": reason,
        },
    )


__all__ = ["BypassRefused", "record_bypass"]
