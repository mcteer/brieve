# SPDX-License-Identifier: Apache-2.0
"""Recording what a model went looking for (036, ADR-0061).

**In core, not in the adapter, and the adapter's own gate is what said so.** The first draft
wrote `DISCOVERY_OBSERVED` from `adapters/pydantic_ai`, and
`test_adapter_holds_no_authority_or_audit_logic` refused it: `append_event` is core-owned,
and an adapter that writes audit directly has reimplemented a core concern (Principle I,
FR-002). The gate was right. The adapter observes a search; deciding what that means for the
trail is the platform's job.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from core.audit.schema import AuditEventType
from core.run import GovernedRun


class DisclosurePosture(StrEnum):
    """Which posture a run is actually in — recorded, never inferred (FR-004, SC-006).

    Three-valued rather than a boolean, and that is the whole point. A run that ASKED for
    deferral and did not get it must not look like one that got it: an operator reading
    `eager` cannot tell whether deferral was never requested or silently failed, and an
    unstated posture is the failure this platform legislates against everywhere else.
    """

    #: Every tool's schema presented up front. Today's behaviour, and the default.
    EAGER = "eager"
    #: Tools cost a catalog line until the model reaches for one.
    DEFERRED = "deferred"
    #: Deferral was requested and could not be composed for this run. Stated, not silent.
    EAGER_FALLBACK = "eager_fallback"


def record_discovery(
    run: GovernedRun,
    *,
    queries: Sequence[str],
    matched: Sequence[str],
    undisclosed_remaining: int,
) -> None:
    """Write that a search happened, and what it found.

    An observation with no decision half: there is no return value, nothing to refuse, and
    no reason code. A search does not consume authority and cannot be declined — disclosure
    changes what a model knows about, never what it may do (ADR-0061, FR-006a).

    Names only. The schemas a search discloses go to the model; the trail gets the names and
    a count, so a record can never become a copy of the tool surface.
    """
    run.audit_sink.append_event(
        correlation_id=run.correlation_id,
        tenant_id=run.tenant_id,
        event_type=AuditEventType.DISCOVERY_OBSERVED,
        payload={
            "queries": list(queries),
            "matched": list(matched),
            # An empty match is written like any other — the search that found nothing is
            # the one most worth reading.
            "undisclosed_remaining": undisclosed_remaining,
        },
    )


__all__ = ["DisclosurePosture", "record_discovery"]
