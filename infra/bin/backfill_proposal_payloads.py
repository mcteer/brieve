#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Clear authored content from checkpoints that reached terminal state before 052 (FR-015).

**A forward-only scrub would leave every run that finished before this feature existed.** The
acceptance signal — `test_row_checkpoints_still_hold_no_credential_material` — sweeps the whole
store rather than runs created after the change, and SC-001 admits no exception for content that
predates the fix. So without this, the feature does not close the issue it was written for.

**Terminal checkpoints only.** A non-terminal one may still be resumed, and clearing it is the
same defect the call-site gating guards against, arriving by a different route.

**The same function the runtime uses.** A second implementation could disagree with the first,
and the whole point is that a backfilled row and a freshly-scrubbed one are indistinguishable
afterwards.

**Reports every blob it changed.** A silent backfill is indistinguishable from one that did
nothing, which is exactly the doubt somebody will have when they run it against a store they
cannot see into.

Usage:
    uv run python infra/bin/backfill_proposal_payloads.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from core.authoring.retention import scrub_proposal_payload  # noqa: E402
from core.durability.types import CheckpointBlob  # noqa: E402
from core.run import RunState  # noqa: E402


def _terminal(blob: Any) -> bool:
    """Whether this run has ended. A resumable one keeps what a resumption would need."""
    outcome = getattr(blob, "outcome", None)
    if outcome is None:
        return False
    try:
        return RunState(str(outcome.state)).is_terminal()
    except ValueError:
        return False


def backfill(provider: Any, *, blob_ids: list[str], dry_run: bool = False) -> list[tuple[str, int]]:
    """Scrub each terminal checkpoint. Returns `(blob_id, files_cleared)` for those changed.

    Idempotent: a blob already scrubbed clears zero and is not reported, so a second run says
    nothing rather than saying it did the work twice.
    """
    changed: list[tuple[str, int]] = []
    for blob_id in blob_ids:
        blob = provider.load(blob_id)
        if blob is None or not _terminal(blob):
            continue
        payload, cleared = scrub_proposal_payload(blob.payload)
        # Compared, not counted. `cleared` counts FILE BODIES; a row whose bodies are already
        # empty but whose `usage` still holds content would report zero and be skipped. That
        # happened the first time the cleared set widened.
        if payload == blob.payload:
            continue
        if not dry_run:
            provider.save(
                CheckpointBlob(
                    blob_id=blob.blob_id,
                    payload=payload,
                    correlation_id=blob.correlation_id,
                    grant_id=blob.grant_id,
                    step_index=blob.step_index,
                    written_by=blob.written_by,
                    outcome=blob.outcome,
                    resume_count=blob.resume_count,
                )
            )
        changed.append((blob_id, cleared))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT / "tests"))
    from tests.conformance.durability import dispatch_harness as h  # noqa: PLC0415
    from tests.harness.operator_credentials import OperatorCredentials  # noqa: PLC0415

    from core.durability.postgres import PostgresDurabilityProvider  # noqa: PLC0415

    conn = h.connection()
    try:
        rows = h.query(
            conn,
            "SELECT blob_id FROM checkpoints "
            "WHERE payload::text LIKE '%authoring_proposal%' ORDER BY blob_id",
        )
    finally:
        conn.close()
    blob_ids = [str(row[0]) for row in rows]

    # The same operator credential the durability lane uses — vended per invocation, never held.
    provider = PostgresDurabilityProvider(credentials=OperatorCredentials())
    print(f"checkpoints holding a proposal: {len(blob_ids)}")
    changed = backfill(provider, blob_ids=blob_ids, dry_run=args.dry_run)

    verb = "would clear" if args.dry_run else "cleared"
    for blob_id, cleared in changed:
        print(f"  {verb} {cleared} file(s) from {blob_id}")
    print(f"{verb} {len(changed)} checkpoint(s)")
    if not changed:
        print("nothing to do — every terminal checkpoint is already scrubbed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
