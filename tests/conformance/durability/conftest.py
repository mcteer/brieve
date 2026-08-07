# SPDX-License-Identifier: Apache-2.0
"""Provider parameterization for the durability rows.

Every row runs against **both** providers. That is the executable form of ADR-0024's
central claim: swapping durability backends changes performance, never whether resume
re-authenticates or whether a checkpoint may hold a credential. If a row needed
rewriting per provider, the claim would be false and the seam drawn in the wrong place.

Postgres failures are loud, never skipped. A row that quietly passes without the real
store would report a guarantee nobody tested.

**There is no development credential path here any more.** The suite obtains its
credential the way the harness does — by presenting its own workload identity — which is
what makes these rows exercise the attestation chain rather than sit beside it. Running
outside a scheduled allocation therefore fails, and that is correct: a process with no
attested identity has no business reaching the state store.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import Iterator

import pytest

from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.postgres import PostgresDurabilityProvider
from core.durability.types import DurabilityProvider

PROVIDERS = ("memory", "postgres")


def _enclave_reachable() -> bool:
    for host, port in (("127.0.0.1", 5432), ("127.0.0.1", 8200)):
        try:
            with socket.create_connection((host, port), timeout=1):
                pass
        except OSError:
            return False
    return True


@pytest.fixture
def run_id(request: pytest.FixtureRequest) -> str:
    """A distinct run id per test **per invocation**.

    Both halves matter, and each was found the hard way against Postgres while the
    in-memory provider stayed green:

    - Distinct per test, or one row's leftover state breaks another.
    - Distinct per invocation, or yesterday's run has already closed today's intents
      and a row asserts against work it did not do.

    Real runs do not share identity either, so this is also the more faithful shape.
    """
    return f"conformance-{request.node.name}-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def postgres_durability() -> Iterator[DurabilityProvider]:
    """The real store only, for a row whose whole subject is that the SQL exists.

    **This fixture was missing and the row using it had therefore never run** — it errored at
    setup with `fixture 'postgres_durability' not found`, inside the allocation lane, where the
    error was one line above a pytest summary that reported the rest of the suite passing.
    Found while wiring 045's endorsed store into the same lane.

    Separate from `provider` rather than a parametrisation of it: `provider` yields memory AND
    postgres, and a row that must speak only about Postgres would then also run against a
    double — which is exactly what its docstring says it exists not to do.
    """
    if not _enclave_reachable():
        pytest.fail(
            "this row is about the SQL and cannot be answered without the store — run "
            "`make dev-up`. Skipping would report a guarantee nobody tested."
        )
    credentials = VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance")
    store = PostgresDurabilityProvider(credentials=credentials)
    store.migrate()
    yield store


@pytest.fixture(params=PROVIDERS)
def provider(request: pytest.FixtureRequest) -> Iterator[DurabilityProvider]:
    if request.param == "memory":
        yield InMemoryDurabilityProvider()
        return

    if not _enclave_reachable():
        pytest.fail(
            "durability conformance requires the local enclave — run `make dev-up`. "
            "These rows are not skippable: a row that passes without the real store "
            "reports a guarantee nobody tested."
        )

    credentials = VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance")
    store = PostgresDurabilityProvider(credentials=credentials)
    store.migrate()
    yield store
