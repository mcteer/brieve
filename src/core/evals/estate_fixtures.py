# SPDX-License-Identifier: Apache-2.0
"""The arranged estate a pack's `estate_state` cases ask about.

**Records, not sentences.** The suite this replaces had no estate at all: the live lane built one
by concatenating the cases' own recorded strings into an unlabelled list, and FR-012's run found
the model correctly refusing to answer from it — nothing said which line described what. Typed
entries with payloads make a question about denials answerable from an entry that says it is about
a denial.

**Authored ids in, content hashes out.** A case cites `rec-vault-002`; the answering path resolves
`entry_hash`. This module owns the translation, so a case author never writes a hash — which they
could not do by hand, and which any edit to the record would invalidate.

**Chained like the real thing.** The entries are hashed with the same `compute_entry_hash` the
sink uses and linked prev→next, so a fixture estate verifies as a chain. A fixture that could not
would be scoring the answering path against material the platform would reject.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.audit.chain import GENESIS_PREV_HASH, compute_entry_hash
from core.audit.schema import AuditEntry, AuditEventType

#: A fixed instant, because the hash covers the timestamp and a fixture whose hashes moved between
#: runs would make every reference unresolvable on the second one.
FIXTURE_EPOCH = datetime(2026, 8, 1, 3, 0, tzinfo=UTC)

FIXTURE_TENANT = "tenant-test"


class EstateFixtureUnusable(Exception):
    """The fixture estate is missing or malformed. Raised, never defaulted to an empty estate.

    An empty estate would make every case decline, and a suite where every case declines can look
    green under a decline-expecting predicate. Loud is the only safe failure here.
    """


@dataclass(frozen=True)
class FixtureEstate:
    """What a pack's estate cases may rest on."""

    records: tuple[AuditEntry, ...]
    #: Authored id → entry hash. What `RecordedEstateProvider` and the scorer translate through.
    ids_to_hashes: dict[str, str]
    #: The inverse, for scoring: the path returns hashes, `case.events` names ids.
    hashes_to_ids: dict[str, str]


def load_estate_records(pack_dir: Path) -> FixtureEstate:
    """Read `estate_records.toml` and build a verifiable chain from it."""
    source = pack_dir / "evals" / "estate_records.toml"
    if not source.exists():
        raise EstateFixtureUnusable(
            f"{source} does not exist; the estate suite has nothing to rest on"
        )
    document = tomllib.loads(source.read_text())
    raw = document.get("records")
    if not isinstance(raw, list) or not raw:
        raise EstateFixtureUnusable(
            f"{source} declares no records; an empty estate answers nothing"
        )

    records: list[AuditEntry] = []
    ids_to_hashes: dict[str, str] = {}
    hashes_to_ids: dict[str, str] = {}
    prev_hash = GENESIS_PREV_HASH

    for seq, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            raise EstateFixtureUnusable(f"{source}: a record is not a table")
        try:
            authored_id = str(entry["id"])
            event_type = AuditEventType(str(entry["event_type"]))
            correlation_id = str(entry["correlation_id"])
        except KeyError as exc:
            raise EstateFixtureUnusable(f"{source}: record missing required field {exc}") from exc
        except ValueError as exc:
            raise EstateFixtureUnusable(
                f"{source}: record {entry.get('id')!r} names an event type this platform does "
                f"not have — a case citing it would be unanswerable for a reason no row explains"
            ) from exc

        if authored_id in ids_to_hashes:
            raise EstateFixtureUnusable(f"{source}: duplicate record id {authored_id!r}")

        payload: dict[str, Any] = dict(entry.get("payload") or {})
        timestamp = FIXTURE_EPOCH
        entry_hash = compute_entry_hash(
            correlation_id=correlation_id,
            tenant_id=FIXTURE_TENANT,
            seq=seq,
            event_type=str(event_type),
            timestamp=timestamp,
            payload=payload,
            prev_hash=prev_hash,
        )
        records.append(
            AuditEntry(
                tenant_id=FIXTURE_TENANT,
                correlation_id=correlation_id,
                seq=seq,
                event_type=event_type,
                timestamp=timestamp,
                payload=payload,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
            )
        )
        ids_to_hashes[authored_id] = entry_hash
        hashes_to_ids[entry_hash] = authored_id
        prev_hash = entry_hash

    return FixtureEstate(
        records=tuple(records), ids_to_hashes=ids_to_hashes, hashes_to_ids=hashes_to_ids
    )


__all__ = [
    "FIXTURE_EPOCH",
    "FIXTURE_TENANT",
    "EstateFixtureUnusable",
    "FixtureEstate",
    "load_estate_records",
]
