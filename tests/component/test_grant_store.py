# SPDX-License-Identifier: Apache-2.0
"""The durable half of ADR-0026, nine features late (014 T007, research F1).

ADR-0026 said consent is *"durable, referenced by a checkpoint via ``grant_id`` only"*.
The referencing half shipped in 005; the durable half did not. So `checkpoints.grant_id`
pointed at nothing for nine features, and `resume_run`'s very first act —
``grant.assert_live(clock)`` — was unevaluable on the dispatched path: there was no record
to load a grant from, so the dispatched entrypoint never even tried.

These rows assert the store the resume path now loads from. They run against the in-memory
provider because that is what a hermetic lane can hold; the Postgres half of the same
protocol is asserted by the durability conformance rows, which is where a claim about
*surviving* anything belongs.
"""

from __future__ import annotations

import json
from datetime import timedelta

from core.authority.grant import issue_grant
from core.authority.types import AuthorityScope
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob
from tests.harness import durability_grant, frozen_clock


def test_a_grant_round_trips_with_its_scope_intact() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = issue_grant(
        subject_user_id="user-1",
        agent_definition_id="definition-1",
        requested_scope=AuthorityScope(
            tool_names=frozenset({"vault_write", "echo"}),
            product_actions=frozenset({"vault:write"}),
        ),
        clock=clock,
        duration=timedelta(hours=1),
    )

    provider.save_grant(grant)
    loaded = provider.load_grant(grant.grant_id)

    assert loaded is not None
    # The SCOPE specifically, not just the id. Resume manufactures fresh authority from
    # `grant.requested_scope`, so a scope that narrowed in the store would silently shrink
    # what a resumed run may do — a refusal at the first step, blamed on the fabric.
    assert loaded.requested_scope.tool_names == frozenset({"vault_write", "echo"})
    assert loaded.requested_scope.product_actions == frozenset({"vault:write"})
    assert loaded.subject_user_id == "user-1"
    assert loaded.agent_definition_id == "definition-1"


def test_a_missing_grant_loads_as_none_rather_than_raising() -> None:
    """Absence is the caller's decision to interpret, mirroring `load()`.

    This is the seam FR-013 rests on: a missing grant is **not** "no consent required",
    and the only code positioned to know that is the caller about to act under it. A
    provider that raised would make the refusal the store's; one that returned an empty
    grant would manufacture consent nobody gave.
    """
    provider = InMemoryDurabilityProvider()
    assert provider.load_grant("never-issued") is None


def test_expiry_is_read_from_the_record() -> None:
    """The bound US4 checks, surviving the round trip.

    Not "the grant is expired" — that is `assert_live`'s row. This asserts the *record*
    carries the instant, because before this table existed the dispatched path had nothing
    to compare a clock against.
    """
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, duration=timedelta(minutes=5))

    provider.save_grant(grant)
    loaded = provider.load_grant(grant.grant_id)

    assert loaded is not None
    assert loaded.expires_at == grant.expires_at
    assert not loaded.is_expired(clock)


def test_consent_is_written_once_and_not_replaced() -> None:
    """A grant's terms do not change; a new consent is a new grant.

    Both providers refuse the mutation — Postgres by `ON CONFLICT DO NOTHING`, this one by
    `setdefault`. An update path would make consent mutable after the fact, so a run could
    execute under terms the record no longer shows.
    """
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    original = durability_grant(clock, tool_names={"echo"}, duration=timedelta(hours=1))
    provider.save_grant(original)

    forged = original.model_copy(
        update={
            "requested_scope": AuthorityScope(tool_names=frozenset({"echo", "vault_write"})),
            "expires_at": original.expires_at + timedelta(days=30),
        }
    )
    provider.save_grant(forged)

    loaded = provider.load_grant(original.grant_id)
    assert loaded is not None
    assert loaded.requested_scope.tool_names == frozenset({"echo"})
    assert loaded.expires_at == original.expires_at


def test_resume_count_survives_save_and_load() -> None:
    """The cap's counter is durable, because it counts disruptions.

    On the checkpoint rather than in memory or in the suspended-run index: memory dies with
    the allocation, and the index row is deleted on dispatch — which is exactly the moment
    the count matters (D3).
    """
    provider = InMemoryDurabilityProvider()
    provider.save(CheckpointBlob(blob_id="run-1", resume_count=3))

    loaded = provider.load("run-1")
    assert loaded is not None
    assert loaded.resume_count == 3


def test_a_later_checkpoint_cannot_lower_the_resume_count() -> None:
    """The H1 wipe, from the store side — and why the store is monotonic.

    `save()` overwrites the whole row, so a per-step blob constructed without the count
    would reset it to zero. That would make the attempt cap a bound that clears itself
    whenever any work happens, and a flapping run immortal: every revival does *some* work
    before re-suspending, so the count would never reach five.

    The resumed run's caller threads the count through every blob it writes, and the
    entrypoint rows assert that. This row asserts the store does not depend on it — the
    difference between a bound that is tested and a bound that is structural (Principle
    III). A superseded zombie holding a stale lower count is the same case and is refused
    by the same comparison.
    """
    provider = InMemoryDurabilityProvider()
    provider.save(CheckpointBlob(blob_id="run-1", resume_count=4))

    provider.save(CheckpointBlob(blob_id="run-1", payload={"step": 0}))

    loaded = provider.load("run-1")
    assert loaded is not None
    assert loaded.resume_count == 4


def test_a_stored_grant_carries_no_credential_shaped_material() -> None:
    """FR-012 extends to the new table by row, not by remark.

    `DelegationGrant` has no field for credential material, so this cannot fail today —
    which is the point of asserting it now. The next person to want "just the credential id,
    for correlation" on this record has to delete a row that says why not, and the reason
    is that `checkpoints.grant_id` already held a credential id once (research F1) and the
    column meant for hours-long consent pointed at something that expired in minutes.
    """
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"vault_write"})
    provider.save_grant(grant)

    loaded = provider.load_grant(grant.grant_id)
    assert loaded is not None
    serialized = json.dumps(loaded.model_dump(mode="json")).lower()

    for forbidden in (
        "password",
        "token",
        "secret",
        "credential",
        "hvs.",  # a Vault token's prefix
        "private_key",
    ):
        assert forbidden not in serialized, f"a grant record must not carry {forbidden!r}"
