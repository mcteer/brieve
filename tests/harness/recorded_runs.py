# SPDX-License-Identifier: Apache-2.0
"""Recorded runs, as entry sequences a report can be compiled from.

**Every `ClaimStatus` value is reachable from something here**, because
`tests/unit/test_report_statuses_are_reachable.py` iterates the enum: a status that exists and
can never be produced fails that row, and one silently merged into another stops being produced
and fails it too.

These are entries, not runs. The compiler takes records and returns a report, so a fixture is a
list of `AuditEntry` — no enclave, no product, no tenant, no HTTP request.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.audit.schema import AuditEntry, AuditEventType
from core.observation.types import ObservationOutcome

TENANT = "tenant-test"


def entry(
    event_type: AuditEventType,
    payload: dict[str, Any],
    *,
    seq: int,
    correlation_id: str = "run-fixture",
) -> AuditEntry:
    """One entry, with the chain fields a compiler reads and nothing it does not.

    `prev_hash` and `entry_hash` are placeholders: the compiler never verifies the chain — that
    is `ReportBasis`'s job, supplied by the caller — so a fixture that computed real digests
    would be asserting something no code under test looks at.
    """
    return AuditEntry(
        correlation_id=correlation_id,
        tenant_id=TENANT,
        seq=seq,
        event_type=event_type,
        timestamp=datetime(2026, 8, 1, tzinfo=UTC),
        payload=payload,
        prev_hash="fixture",
        entry_hash="fixture",
    )


def _tool_ran(step: int, tool: str, seq: int) -> list[AuditEntry]:
    return [
        entry(
            AuditEventType.TOOL_CHOSEN,
            {"step_index": step, "named": tool, "model": "fixture/scripted@1", "outcome": "named"},
            seq=seq,
        ),
        entry(AuditEventType.TOOL_OUTCOME, {"step_index": step, "tool_name": tool}, seq=seq + 1),
    ]


def _observed(step: int, tool: str, outcome: ObservationOutcome, seq: int) -> AuditEntry:
    return entry(
        AuditEventType.EFFECT_OBSERVED,
        {
            "step_index": step,
            "tool": tool,
            "idempotency_key": f"run-fixture:{step}:{tool}",
            "outcome": str(outcome),
            "detail": "fixture",
        },
        seq=seq,
    )


def clean_run() -> list[AuditEntry]:
    """A run that did its work and confirmed it. Reaches `from_record` and `observed`."""
    return [
        entry(AuditEventType.RUN_START, {}, seq=0),
        *_tool_ran(0, "vault_write", 1),
        _observed(0, "vault_write", ObservationOutcome.HAPPENED, 3),
    ]


def run_with_a_denial() -> list[AuditEntry]:
    """A tool the ceiling refused. Reaches `from_record`.

    FR-003: a report that omits what was refused describes a different run.
    """
    return [
        entry(AuditEventType.RUN_START, {}, seq=0),
        entry(
            AuditEventType.TOOL_CHOSEN,
            {"step_index": 0, "named": "apply", "model": "fixture/scripted@1", "outcome": "named"},
            seq=1,
        ),
        entry(
            AuditEventType.PRE_DECISION,
            {"hook_name": "authority", "outcome": "deny", "reason_code": "out_of_scope"},
            seq=2,
        ),
    ]


def contradicted_effect() -> list[AuditEntry]:
    """The product was asked and said it did not land. Reaches `contradicted`.

    **The failure ADR-0018 opens with.** A tool outcome recorded as allowed, and an effect that
    is not there.
    """
    return [
        entry(AuditEventType.RUN_START, {}, seq=0),
        *_tool_ran(0, "vault_write", 1),
        _observed(0, "vault_write", ObservationOutcome.DID_NOT_HAPPEN, 3),
    ]


def unreachable_product() -> list[AuditEntry]:
    """The run tried to observe and could not reach the product. Reaches
    `unverified_unreachable`."""
    return [
        entry(AuditEventType.RUN_START, {}, seq=0),
        *_tool_ran(0, "vault_write", 1),
        _observed(0, "vault_write", ObservationOutcome.CANNOT_DETERMINE, 3),
    ]


def tool_without_an_observer() -> list[AuditEntry]:
    """An effect on a tool nothing can ask about. Reaches `unverified_no_observer`.

    Compile with `observers=frozenset()` — the absence is a fact about the tool's registration,
    not about the product.
    """
    return [
        entry(AuditEventType.RUN_START, {}, seq=0),
        *_tool_ran(0, "echo", 1),
    ]


def killed_before_terminal() -> list[AuditEntry]:
    """A run that never got to observe. Reaches `unverified_not_observed`.

    Compile with `terminal=False` and an observer registered: a killed run and a down product
    are different facts, and this is the one that says nobody ever asked.
    """
    return [
        entry(AuditEventType.RUN_START, {}, seq=0),
        *_tool_ran(0, "vault_write", 1),
    ]


def unrecognised_record() -> list[AuditEntry]:
    """A record type the compiler does not interpret. Reaches `unreconciled`.

    `TURN_RECORDED` is a real member the report compiler has no claim shape for — a genuine
    unknown rather than an invented one, which is what makes this fixture honest about the
    failure it represents: the trail getting richer than the compiler.
    """
    return [
        entry(AuditEventType.RUN_START, {}, seq=0),
        entry(AuditEventType.TURN_RECORDED, {"message": "fixture"}, seq=1),
    ]


def refused_before_starting() -> list[AuditEntry]:
    """Authority refused; the run never began. Reaches `from_record`.

    Its disposition must be `refused` rather than `running` — there is no terminal record
    because there was never a run, and reading that absence as in-flight leaves it that way
    forever.
    """
    return [
        entry(AuditEventType.AUTHORITY_REFUSED, {"reason_code": "authority_refused"}, seq=0),
    ]


def resumed_run() -> list[AuditEntry]:
    """A revived run whose prefix was re-observed. Reaches `from_record`.

    A report reading `STEP_REOBSERVED` as a gap would describe every resumed run as incomplete.
    """
    return [
        entry(
            AuditEventType.RUN_RESUMED, {"attempt": 1, "outcome": "continued", "reason": ""}, seq=0
        ),
        entry(
            AuditEventType.STEP_REOBSERVED, {"step_index": 0, "reason": "result_recorded"}, seq=1
        ),
        *_tool_ran(1, "vault_write", 2),
        _observed(1, "vault_write", ObservationOutcome.HAPPENED, 4),
    ]


def model_chose_nothing() -> list[AuditEntry]:
    """020's terminal outcome: the model named no tool. Reaches `from_record`."""
    return [
        entry(AuditEventType.RUN_START, {}, seq=0),
        entry(
            AuditEventType.TOOL_CHOSEN,
            {"step_index": 0, "named": "", "model": "fixture/scripted@1", "outcome": "empty"},
            seq=1,
        ),
    ]


#: Every fixture, for rows that need to sweep them.
ALL_FIXTURES = (
    clean_run,
    run_with_a_denial,
    contradicted_effect,
    unreachable_product,
    tool_without_an_observer,
    killed_before_terminal,
    unrecognised_record,
    refused_before_starting,
    resumed_run,
    model_chose_nothing,
)

__all__ = [
    "ALL_FIXTURES",
    "TENANT",
    "clean_run",
    "contradicted_effect",
    "entry",
    "killed_before_terminal",
    "model_chose_nothing",
    "recorded_run_ids",
    "refused_before_starting",
    "resumed_run",
    "run_with_a_denial",
    "tool_without_an_observer",
    "unreachable_product",
    "unrecognised_record",
]


def recorded_run_ids() -> tuple[str, ...]:
    """Fixture names, for parametrised row ids."""
    return tuple(fixture.__name__ for fixture in ALL_FIXTURES)
