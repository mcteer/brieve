# SPDX-License-Identifier: Apache-2.0
"""In-memory durability provider.

Survives 005 as a **test double for suites that are not about durability**. The
durability conformance rows run against Postgres — a provider that keeps state in a
dict cannot demonstrate that state survived anything.

It implements the full protocol anyway, so the same conformance rows can run against
both and prove they are written to the seam rather than to an implementation (FR-012).
"""

from __future__ import annotations

from core.durability.types import CheckpointBlob, IntentRecord, ResultRecord


class InMemoryDurabilityProvider:
    """Process-local store. No persistence, no credentials."""

    def __init__(self) -> None:
        self._blobs: dict[str, CheckpointBlob] = {}
        self._leases: dict[str, str] = {}
        self._intents: dict[tuple[str, str], IntentRecord] = {}
        self._results: set[tuple[str, str]] = set()

    def save(self, blob: CheckpointBlob) -> None:
        self._blobs[blob.blob_id] = blob

    def load(self, blob_id: str) -> CheckpointBlob | None:
        return self._blobs.get(blob_id)

    def acquire_lease(self, run_id: str, holder_identity: str) -> None:
        # Unconditional overwrite is the correct semantic: a new holder supersedes the
        # old. Refusing here would make a resumed run lose to the zombie it replaces.
        self._leases[run_id] = holder_identity

    def check_lease(self, run_id: str, holder_identity: str) -> bool:
        return self._leases.get(run_id) == holder_identity

    def record_intent(self, record: IntentRecord) -> None:
        self._intents[(record.run_id, record.idempotency_key)] = record

    def record_result(self, record: ResultRecord) -> None:
        self._results.add((record.run_id, record.idempotency_key))

    def open_intents(self, run_id: str) -> list[IntentRecord]:
        return [
            record
            for (rid, key), record in sorted(self._intents.items())
            if rid == run_id and (rid, key) not in self._results
        ]
