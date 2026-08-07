# SPDX-License-Identifier: Apache-2.0
"""Removing measurement policies a dead run left behind (042, FR-023).

**"Always destroyed" is a claim, and this is what makes it checkable.** `vault_policy_impact`
destroys its scratch policies in a `finally`, so the ordinary path and every failing path both
clean up. What neither can cover is a process that stops existing between the write and the
`finally` — a kill, an OOM, a node going away — and that leaves a policy nobody decided to
create standing in the trust fabric.

**Beside the resume sweeper, and for the same reason.** The persistent MCP service already
hosts the resume sweeper and the dependency checks because both needed a long-lived home. An
orphan is the same shape of problem: something a dead run left that only a living process can
clear. Sweeping from the run itself would be asking the case that cannot run to handle itself.

**The grant is the service's alone.** Finding an orphan means finding a name nobody told you
about, so the sweep needs `list` over the policy namespace — which is exactly why a dispatched
run must not have it. `scratch_sweep` is attached to the service role; `scratch_policy_check`,
which carries no `list`, is what a run gets.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from core.audit.schema import AuditEventType

#: The measurement namespace, and the only thing this sweep will delete. Named here as well as
#: in `scratch.tf` and `policy_authoring.py` because a sweeper that took its prefix from a
#: caller would be a delete loop with a configurable target.
SCRATCH_PREFIX = "scratch-agent-"

POLICY_ROOT = "sys/policies/acl"


@dataclass(frozen=True)
class SweepOutcome:
    """What one pass found and what it did about it."""

    examined: int
    removed: tuple[str, ...]
    live_skipped: tuple[str, ...]


def _run_id_of(policy_name: str) -> str:
    """`scratch-agent-<run>-current` → `<run>`.

    The suffix is stripped from the RIGHT because a correlation id may itself contain a
    hyphen — `corr-042-ceiling` does — and splitting from the left would attribute a policy
    to a run that does not exist and then decline to sweep it forever.
    """
    stem = policy_name.removeprefix(SCRATCH_PREFIX)
    for suffix in ("-current", "-proposed"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def sweep_scratch_policies(
    *,
    list_policies: Callable[[], Iterable[str]],
    delete_policy: Callable[[str], None],
    is_live: Callable[[str], bool],
    audit: Any = None,
    tenant_id: str = "",
) -> SweepOutcome:
    """Remove measurement policies whose run is gone. Returns what it did.

    **A live run's policies are left alone**, which is the difference between a sweep and a
    race: an impact check in flight is exactly a scratch policy whose run is alive, and
    deleting it would break the measurement it was created for and report a capability set
    that never existed.

    **A delete that fails is not fatal.** One policy the fabric refused should not stop the
    pass from clearing the other nine — an orphan left because an unrelated one was stuck is
    an orphan the next pass has to find again.

    The removal is audited because a policy disappearing from the trust fabric with no record
    is indistinguishable, later, from one that was never created.
    """
    examined = 0
    removed: list[str] = []
    live: list[str] = []

    for name in list_policies():
        if not name.startswith(SCRATCH_PREFIX):
            continue
        examined += 1
        run_id = _run_id_of(name)
        if run_id and is_live(run_id):
            live.append(name)
            continue
        try:
            delete_policy(f"{POLICY_ROOT}/{name}")
        except Exception:  # noqa: BLE001 — one stuck policy must not end the pass
            continue
        removed.append(name)

    if removed and audit is not None:
        audit.append_event(
            correlation_id="scratch-sweep",
            tenant_id=tenant_id,
            event_type=AuditEventType.CONTAINMENT_REFUSED,
            payload={
                "code": "orphaned_scratch_policy_removed",
                "policies": sorted(removed),
                "count": len(removed),
            },
        )

    return SweepOutcome(
        examined=examined, removed=tuple(sorted(removed)), live_skipped=tuple(sorted(live))
    )


__all__ = ["POLICY_ROOT", "SCRATCH_PREFIX", "SweepOutcome", "sweep_scratch_policies"]
