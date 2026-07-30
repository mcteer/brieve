# SPDX-License-Identifier: Apache-2.0
"""Aggregate counters — the skill-authoring backlog, measured rather than guessed.

ADR-0031's claim is that **what the agent had to look up, and how often, ranks what to
distil into skills next**. A section whose retrieval rate falls after a pack release is
evidence the distillation worked; one that stays high is the next skill to write. Skill
authoring stops being faith-based the moment there is a number.

**A counter, not a table** (Principle VI: nothing blocking that could be a library, a signed
cache, or an async emitter). The ranking is read at a lifecycle review, not by a run, so
nothing needs it queryable in-process — and a new Postgres table would be an operated
component for something OTel already carries.

**Counters rather than span attributes**, decided rather than left open. Both satisfy
ADR-0031 in principle, but the ADR wants a *ranking*: a counter is read directly, while span
attributes make it a query over traces at review time. The cheaper thing to read is the thing
that gets read.

**No target content ever reaches a counter.** Attributes are the retrieval *target* — a URL
or a section identifier — and never what was found there. A counter is unredacted by nature
and is exported to wherever telemetry goes, which is a different trust boundary from the
audit trail.
"""

from __future__ import annotations

from typing import Any

from opentelemetry import metrics

_METER_NAME = "core.retrieval"

#: What was looked up, and how often. The whole of ADR-0031's mechanism.
RETRIEVAL_COUNTER = "retrieval.target.reads"

_meter: metrics.Meter | None = None
_counters: dict[str, Any] = {}


def _counter(name: str, description: str) -> Any:
    """One instrument per name, created lazily.

    Lazily because creating instruments at import time would make importing `core` reach the
    metrics SDK — and the base install deliberately carries `opentelemetry-api` without a
    configured exporter. With no SDK the API's no-op meter is used and nothing is emitted,
    which is the correct behaviour for a platform that has not been told where to send
    telemetry.
    """
    global _meter
    if _meter is None:
        _meter = metrics.get_meter(_METER_NAME)
    if name not in _counters:
        _counters[name] = _meter.create_counter(name, description=description)
    return _counters[name]


def record_retrieval(target: str, *, pack: str = "", section: str = "") -> None:
    """Count one retrieval of a guidance target.

    ``target`` is *what was looked up* — a URL or document identifier — and never what it
    said. The distinction is load-bearing: the audit trail carries the content hash under
    the run's own salt, and this carries only the fact that a lookup happened.

    Failures are swallowed on purpose. A telemetry emitter that could fail a run would make
    the backlog mechanism a reliability dependency of every retrieval, and ADR-0031's
    ranking is worth strictly less than the run it would break.
    """
    try:
        _counter(RETRIEVAL_COUNTER, "Reads of a consulted guidance target (ADR-0031)").add(
            1, {"target": target, "pack": pack, "section": section}
        )
    except Exception:  # noqa: BLE001 — telemetry must never fail the thing it observes
        pass


__all__ = ["RETRIEVAL_COUNTER", "record_retrieval"]
