# SPDX-License-Identifier: Apache-2.0
"""In-memory durability provider.

Survives 005 as a **test double for suites that are not about durability**. The
durability conformance rows run against Postgres — a provider that keeps state in a
dict cannot demonstrate that state survived anything.

It implements the full protocol anyway, so the same conformance rows can run against
both and prove they are written to the seam rather than to an implementation (FR-012).
"""

from __future__ import annotations

from core.authority.grant import DelegationGrant
from core.durability.types import CheckpointBlob, IntentRecord, ResultRecord


class InMemoryDurabilityProvider:
    """Process-local store. No persistence, no credentials."""

    def __init__(self) -> None:
        self._blobs: dict[str, CheckpointBlob] = {}
        self._leases: dict[str, str] = {}
        self._intents: dict[tuple[str, str], IntentRecord] = {}
        self._results: set[tuple[str, str]] = set()
        self._grants: dict[str, DelegationGrant] = {}

    def save(self, blob: CheckpointBlob) -> None:
        # TERMINAL-ONCE, matching the Postgres provider's COALESCE guard. The two must
        # agree here or a row proven against one says nothing about the other — and this is
        # precisely the property a hermetic row would be used to prove.
        #
        # A terminal outcome, once recorded, survives every later write. Without this a
        # routine checkpoint (which carries no outcome) erases a stop and resurrects the
        # run, which is what shipped for three features before anyone read the SQL.
        # Note the condition: an existing terminal outcome survives ANY later write, not
        # only one that carries none. That is what `COALESCE(checkpoints.run_state, ...)`
        # does, and writing the narrower version here made the two providers disagree on
        # precisely the stop-versus-finish race the guard exists for — caught by the row
        # that asserts the first terminal write wins.
        existing = self._blobs.get(blob.blob_id)
        if existing is not None and existing.outcome is not None:
            blob = blob.model_copy(update={"outcome": existing.outcome})
        # MONOTONIC resume_count, matching the Postgres provider's GREATEST. Same rule as
        # the terminal-once guard above and the same reason it is repeated here: a property
        # proven against one provider says nothing about the other, and the divergence
        # would be found by whichever row happened to run against Postgres — which for the
        # revival cap is the flap row, the slowest one in the suite.
        if existing is not None and existing.resume_count > blob.resume_count:
            blob = blob.model_copy(update={"resume_count": existing.resume_count})
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

    def scrub_closed_arguments(self, run_id: str) -> int:
        """Clear arguments on closed brackets. See the protocol for why closed only.

        **The in-memory provider round-trips this for free**, which is exactly why 040's M7
        exists: a row proven here says nothing about the SQL. The Postgres leg is the one that
        counts, and the conformance row runs both.
        """
        scrubbed = 0
        for key, record in list(self._intents.items()):
            if key[0] != run_id or key not in self._results:
                continue
            if record.arguments is not None:
                self._intents[key] = record.model_copy(update={"arguments": None})
                scrubbed += 1
        return scrubbed

    def closed_intents(self, run_id: str) -> list[IntentRecord]:
        return [
            record
            for (rid, key), record in sorted(self._intents.items())
            if rid == run_id and (rid, key) in self._results
        ]

    def save_grant(self, grant: DelegationGrant) -> None:
        # Written once, like the Postgres provider's ON CONFLICT DO NOTHING. A grant's
        # terms do not change, so a re-save of a known id keeps the recorded consent
        # rather than replacing it — otherwise a hermetic row could demonstrate a mutation
        # the real store would refuse.
        self._grants.setdefault(grant.grant_id, grant)

    def load_grant(self, grant_id: str) -> DelegationGrant | None:
        return self._grants.get(grant_id)
