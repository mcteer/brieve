# SPDX-License-Identifier: Apache-2.0
"""Row: an approved claim mapping is found again, and grants its role.

The neighbouring row (`test_claim_mapping_gated`) proves a mapping change is really
gated. This one proves the other half — that a mapping which survives the gate is **read
back**, because until now nothing read them at all and the surface refused every
authenticated request as a result.

**On the real path, under the real policy, not a throwaway mount.** A scratch mount would
have tested a reader against grants nobody deployed, and the grant is half the mechanism:
KV v2 needs `list` on the metadata path as a capability distinct from `read` on the data
path, and without it Vault answers 403 — which a reader could easily mistake for "no
mappings are configured". A row on a mount the conformance role happened to be allowed to
read would go green against a policy that does not exist in production. This one goes red.

Records are namespaced by a per-run uuid claim value and destroyed afterwards, so the row
grants nothing real even while it is running: the claim value it maps is one no token
carries.

The other reason a fake cannot stand in here is that KV v2 splits reading from listing.
Data lives at ``mount/data/prefix/key`` and key names at ``mount/metadata/prefix``. An
in-memory double answers both from one dict and passes whichever paths the reader asks
for, so the single mistake that makes this component discover nothing in production is
exactly the mistake it cannot catch.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.identity.claims import ClaimMapping, resolve_roles
from core.identity.mappings_store import ClaimMappingsUnavailable, VaultClaimMappings
from surfaces.api.authority_submit import VaultAuthoritySubmitter
from tests.harness.vault_control_groups import VaultAdmin, reachable

# `host_enclave`: setting up and cleaning up records needs an admin token, which the
# conformance allocation deliberately does not carry.
pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

#: The path the API assembly configures, from `infra/jobs/api.nomad.hcl`. A literal rather
#: than an import so that a change to the deployed default has to be made in both places
#: on purpose — a shared constant would let the row follow the surface somewhere the
#: policy does not reach, and still pass.
DATA_PATH = "harness-authority/data/claim-mappings"
METADATA_PATH = "harness-authority/metadata/claim-mappings"

CLAIM = "https://brieve.dev/roles"


@pytest.fixture
def admin() -> VaultAdmin:
    if not reachable():
        pytest.fail(
            "the control-plane Vault is unreachable — run `make dev-up`. Not skippable: "
            "a mapping store nobody read from is how this component shipped broken."
        )
    return VaultAdmin()


@pytest.fixture
def scratch(admin: VaultAdmin) -> Iterator[list[ClaimMapping]]:
    """Mappings written by a test, destroyed afterwards whatever happens.

    Destroyed rather than deleted: KV v2 keeps a deleted version's metadata, so the key
    keeps appearing in a LIST. Leaving them would make the next run's "how many mappings
    are there" assertions depend on every previous run.
    """
    written: list[ClaimMapping] = []
    try:
        yield written
    finally:
        for mapping in written:
            key = VaultAuthoritySubmitter(controlled_path=DATA_PATH, token=admin.token).record_path(
                mapping
            )
            admin.request(
                f"{METADATA_PATH}/{key.removeprefix(f'{DATA_PATH}/')}",
                method="DELETE",
            )


def a_mapping(role: str = "operator") -> ClaimMapping:
    """A mapping no real token can satisfy — the claim value is unique to this run."""
    return ClaimMapping(claim_name=CLAIM, claim_value=f"conformance-{uuid.uuid4().hex}", role=role)


def reader(**kwargs: object) -> VaultClaimMappings:
    """The reader the API assembly builds: data path in, metadata path derived.

    `ttl_seconds=0` because the cache has its own component coverage and a row that
    waited out a TTL would be measuring the clock rather than Vault.
    """
    return VaultClaimMappings(
        credentials=VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance"),
        data_path=DATA_PATH,
        ttl_seconds=0.0,
        **kwargs,  # type: ignore[arg-type]
    )


def submit(admin: VaultAdmin, scratch: list[ClaimMapping], mapping: ClaimMapping) -> None:
    scratch.append(mapping)
    VaultAuthoritySubmitter(controlled_path=DATA_PATH, token=admin.token).submit(
        requester="conformance@example.test", mapping=mapping
    )


def test_a_submitted_mapping_is_found_again(admin: VaultAdmin, scratch: list[ClaimMapping]) -> None:
    """The loop, closed, against the real path under the deployed policy.

    Ungated here on purpose — the gate has its own row. What this asserts is that the
    path the submitter writes to is the path the reader looks in, and that the workload
    is actually permitted to look, which is a claim about deployment and not approval.
    """
    mapping = a_mapping()
    submit(admin, scratch, mapping)

    mappings = reader().current()

    assert mapping in mappings, (
        f"submitted mapping was not read back. Found {len(mappings)} mapping(s) at "
        f"{DATA_PATH} — an empty result here usually means the workload lacks `list` on "
        f"{METADATA_PATH}, which Vault reports as 403 rather than as an empty folder."
    )
    assert resolve_roles({CLAIM: [mapping.claim_value], "sub": "u1"}, mappings) == frozenset(
        {"operator"}
    )


def test_a_second_mapping_does_not_displace_the_first(
    admin: VaultAdmin, scratch: list[ClaimMapping]
) -> None:
    """What one-record-per-path cost, demonstrated where it actually happened.

    Both mappings landed on the configured path itself, so approving the second silently
    revoked the first — granting one person a role by taking someone else's away. Against
    real Vault because a KV v2 write REPLACES the secret at that path, and no in-memory
    double is obliged to behave that way.
    """
    first, second = a_mapping("operator"), a_mapping("reviewer")
    submit(admin, scratch, first)
    submit(admin, scratch, second)

    mappings = reader().current()

    assert first in mappings
    assert second in mappings


def test_resubmitting_a_mapping_does_not_duplicate_it(
    admin: VaultAdmin, scratch: list[ClaimMapping]
) -> None:
    """A derived key means a re-request lands on the record it already occupies.

    Otherwise every submission accumulates a copy, and revoking the grant means finding
    all of them — with any that were missed still granting the role.
    """
    mapping = a_mapping()
    submit(admin, scratch, mapping)
    VaultAuthoritySubmitter(controlled_path=DATA_PATH, token=admin.token).submit(
        requester="someone-else@example.test", mapping=mapping
    )

    assert [m for m in reader().current() if m == mapping] == [mapping]


def test_a_revoked_mapping_stops_granting(admin: VaultAdmin, scratch: list[ClaimMapping]) -> None:
    """Revocation has to take effect, or the grant outlives the decision to remove it."""
    mapping = a_mapping()
    submit(admin, scratch, mapping)
    assert mapping in reader().current()

    key = (
        VaultAuthoritySubmitter(controlled_path=DATA_PATH, token=admin.token)
        .record_path(mapping)
        .removeprefix(f"{DATA_PATH}/")
    )
    admin.request(f"{METADATA_PATH}/{key}", method="DELETE")

    assert mapping not in reader().current()


def test_a_prefix_the_workload_may_not_list_refuses() -> None:
    """The failure the `list` capability exists to make visible.

    Vault answers 403 for a prefix the token holds no grant on — NOT 404 — so a reader
    that mapped every failure to "no mappings are configured" would refuse every token
    while reporting a correctly empty estate, and whoever investigated would go looking
    at claim configuration instead of at a policy.

    `harness-authority` is mounted and readable in part; this prefix is not granted, so
    the refusal comes from the policy rather than from an unreachable Vault.
    """
    unlisted = VaultClaimMappings(
        credentials=VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance"),
        data_path="harness-authority/data/claim-mappings-not-granted",
        ttl_seconds=0.0,
    )

    with pytest.raises(ClaimMappingsUnavailable):
        unlisted.current()
