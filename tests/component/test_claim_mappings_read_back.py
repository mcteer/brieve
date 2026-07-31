# SPDX-License-Identifier: Apache-2.0
"""The read end of the claim-mapping loop.

The mechanism these cover was written, tested and wired to nothing: mappings could be
submitted for approval, but the verifier was constructed without any, so `resolve_roles`
returned empty and every authenticated request was refused. The tests worth having are
therefore about the loop CLOSING — a mapping written by the submitter must be found by
the reader — and about the two ways a reader can be quietly wrong: reporting an outage as
an empty grant set, and serving a mapping past its revocation.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.identity.claims import ClaimMapping, resolve_roles
from core.identity.mappings_store import (
    ClaimMappingsUnavailable,
    VaultClaimMappings,
    mapping_key,
)

DATA_PATH = "harness-authority/data/claim-mappings"
METADATA_PATH = "harness-authority/metadata/claim-mappings"

OPERATOR = ClaimMapping(
    claim_name="https://brieve.dev/roles", claim_value="platform-operator", role="operator"
)
REVIEWER = ClaimMapping(
    claim_name="https://brieve.dev/roles", claim_value="platform-reviewer", role="reviewer"
)


class FakeVault:
    """A KV v2 mount, only as far as this needs one."""

    def __init__(self, records: dict[str, dict[str, Any]] | None = None) -> None:
        self.records = dict(records or {})
        self.list_error: Exception | None = None
        self.read_error: Exception | None = None
        self.reads = 0

    def write(self, key: str, record: dict[str, Any]) -> None:
        self.records[key] = record

    def list_path(self, path: str, *, token: str | None = None) -> list[str] | None:
        if self.list_error is not None:
            raise self.list_error
        assert path == METADATA_PATH, f"listed {path!r}, which is not the metadata path"
        return sorted(self.records) or None

    def read_path(self, path: str, *, token: str | None = None) -> dict[str, Any] | None:
        if self.read_error is not None:
            raise self.read_error
        self.reads += 1
        prefix = f"{DATA_PATH}/"
        assert path.startswith(prefix), f"read {path!r}, which is not under the data path"
        record = self.records.get(path[len(prefix) :])
        return {"data": {"data": record}} if record is not None else None


def store(vault: FakeVault, **kwargs: Any) -> VaultClaimMappings:
    return VaultClaimMappings(credentials=vault, data_path=DATA_PATH, **kwargs)


def as_record(mapping: ClaimMapping, requester: str = "someone@example.test") -> dict[str, Any]:
    return {
        "claim_name": mapping.claim_name,
        "claim_value": mapping.claim_value,
        "role": mapping.role,
        "requested_by": requester,
    }


def test_an_approved_mapping_grants_its_role() -> None:
    """The loop, end to end: written under a submitter key, read back, resolves."""
    vault = FakeVault()
    vault.write(mapping_key(OPERATOR), as_record(OPERATOR))

    mappings = store(vault).current()

    assert mappings == [OPERATOR]
    claims = {"https://brieve.dev/roles": ["platform-operator"], "sub": "u1"}
    assert resolve_roles(claims, mappings) == frozenset({"operator"})


def test_two_mappings_coexist() -> None:
    """The bug the per-mapping key exists to prevent.

    Both mappings written to one path meant the second silently replaced the first, so
    granting one role revoked another. Distinct keys are what make that impossible, and
    the assertion that matters is that BOTH survive.
    """
    vault = FakeVault()
    vault.write(mapping_key(OPERATOR), as_record(OPERATOR))
    vault.write(mapping_key(REVIEWER), as_record(REVIEWER))

    assert mapping_key(OPERATOR) != mapping_key(REVIEWER)
    assert set(store(vault).current()) == {OPERATOR, REVIEWER}


def test_the_key_is_stable_across_submissions() -> None:
    """Re-submitting a mapping targets the record it already occupies, not a new one."""
    assert mapping_key(OPERATOR) == mapping_key(
        ClaimMapping(
            claim_name="https://brieve.dev/roles",
            claim_value="platform-operator",
            role="operator",
        )
    )


def test_a_namespaced_claim_does_not_nest_the_record() -> None:
    """Auth0 and Okta emit URI claim names. A key carrying one would create folders."""
    assert "/" not in mapping_key(OPERATOR)
    assert ":" not in mapping_key(OPERATOR)


def test_an_estate_with_no_mappings_grants_nothing() -> None:
    """A legitimate state, and it refuses — an estate that granted nobody anything."""
    assert store(FakeVault()).current() == []


def test_an_unreachable_fabric_is_not_an_empty_grant_set() -> None:
    """The failure this module exists to keep distinguishable.

    Both produce no roles and refuse every token, but one is a configuration state and
    the other is an outage. Returning `[]` here would send whoever investigates to look
    at claim configuration during a Vault incident.
    """
    vault = FakeVault()
    vault.list_error = OSError("connection refused")

    with pytest.raises(ClaimMappingsUnavailable):
        store(vault).current()


def test_a_listed_record_that_cannot_be_read_refuses() -> None:
    """A partial mapping set must never be presented as the whole set.

    Skipping the unreadable record would resolve the token against a subset of the
    approved grants — quietly denying a role somebody holds, with nothing to indicate
    the answer was incomplete.
    """
    vault = FakeVault()
    vault.write(mapping_key(OPERATOR), as_record(OPERATOR))
    vault.records["ghost"] = {}
    vault.records.pop("ghost")
    vault.records["ghost"] = {"claim_name": "x"}  # listed, missing claim_value and role

    with pytest.raises(ClaimMappingsUnavailable):
        store(vault).current()


def test_an_approved_mapping_takes_effect_without_a_restart() -> None:
    """The reason the verifier resolves per call rather than at construction."""
    vault = FakeVault()
    now = [0.0]
    mappings = store(vault, ttl_seconds=60.0, clock=lambda: now[0])

    assert mappings.current() == []

    vault.write(mapping_key(OPERATOR), as_record(OPERATOR))
    now[0] = 61.0

    assert mappings.current() == [OPERATOR]


def test_a_revoked_mapping_stops_granting() -> None:
    vault = FakeVault()
    vault.write(mapping_key(OPERATOR), as_record(OPERATOR))
    now = [0.0]
    mappings = store(vault, ttl_seconds=60.0, clock=lambda: now[0])
    assert mappings.current() == [OPERATOR]

    vault.records.clear()
    now[0] = 61.0

    assert mappings.current() == []


def test_a_fresh_cache_does_not_re_read() -> None:
    """A token check must not be a Vault round trip on the hot path."""
    vault = FakeVault()
    vault.write(mapping_key(OPERATOR), as_record(OPERATOR))
    now = [0.0]
    mappings = store(vault, ttl_seconds=60.0, clock=lambda: now[0])

    mappings.current()
    reads = vault.reads
    now[0] = 30.0
    mappings.current()

    assert vault.reads == reads


def test_the_submitter_writes_where_the_reader_looks() -> None:
    """The halves must agree on the path, or the loop is open in a new place.

    Taken from the submitter's own answer rather than recomputed here: a test that
    derived the key the same way the code does would drift along with it, and the
    failure being guarded is precisely the two ends drifting apart.
    """
    from surfaces.api.authority_submit import VaultAuthoritySubmitter

    submitter = VaultAuthoritySubmitter(
        vault_addr="https://vault.test:8200", controlled_path=DATA_PATH
    )
    written = submitter.record_path(OPERATOR)

    assert written.startswith(f"{DATA_PATH}/")
    vault = FakeVault()
    vault.write(written.removeprefix(f"{DATA_PATH}/"), as_record(OPERATOR))

    assert store(vault).current() == [OPERATOR]


def test_an_expired_cache_and_an_unreachable_fabric_refuse() -> None:
    """Fails closed rather than serving the stale set.

    The same choice `_KeyCache` makes for signing material. A mapping that outlived its
    revocation because the fabric blinked is a grant nobody approved.
    """
    vault = FakeVault()
    vault.write(mapping_key(OPERATOR), as_record(OPERATOR))
    now = [0.0]
    mappings = store(vault, ttl_seconds=60.0, clock=lambda: now[0])
    assert mappings.current() == [OPERATOR]

    vault.list_error = OSError("connection refused")
    now[0] = 61.0

    with pytest.raises(ClaimMappingsUnavailable):
        mappings.current()
