# SPDX-License-Identifier: Apache-2.0
"""Fixtures for the API conformance rows.

**No development credential path exists here.** These fixtures obtain credentials the way
the harness does — by presenting a workload identity — which is what makes the rows
exercise the attestation chain rather than sit beside it. Running outside a scheduled
allocation therefore fails, and that is correct.

Two distinct credentials, drawn from two distinct Vault roles, because the point of most
of these rows is the difference between them: the harness role can write the evidence
store, and the evidence role can only read it.
"""

from __future__ import annotations

import socket
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from core.audit.postgres_query import PostgresEvidenceQuery
from core.audit.postgres_sink import PostgresAuditSink
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials

TENANT = "tenant-conformance"
EVIDENCE_CREDS_PATH = "database/creds/evidence"


def _enclave_reachable() -> bool:
    for host, port in (("127.0.0.1", 5432), ("127.0.0.1", 8200)):
        try:
            with socket.create_connection((host, port), timeout=1):
                pass
        except OSError:
            return False
    return True


def _require_enclave() -> None:
    if not _enclave_reachable():
        pytest.fail(
            "API evidence rows require the local enclave — run `make dev-up`. "
            "Not skippable: a row that passes without the real store reports a "
            "guarantee nobody tested."
        )


@pytest.fixture
def run_credentials() -> VaultDatabaseCredentials:
    """The harness role — the one that can write."""
    _require_enclave()
    return VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance")


@pytest.fixture
def evidence_credentials() -> VaultDatabaseCredentials:
    """The SELECT-only evidence role."""
    _require_enclave()
    return VaultDatabaseCredentials(
        identity=NomadWorkloadIdentity(),
        role="conformance",
        creds_path=EVIDENCE_CREDS_PATH,
    )


@pytest.fixture
def audit_sink(run_credentials: VaultDatabaseCredentials) -> PostgresAuditSink:
    sink = PostgresAuditSink(credentials=run_credentials)
    sink.migrate()
    return sink


@pytest.fixture
def evidence_query(evidence_credentials: VaultDatabaseCredentials) -> PostgresEvidenceQuery:
    return PostgresEvidenceQuery(credentials=evidence_credentials)


@pytest.fixture
def evidence_connection(evidence_credentials: VaultDatabaseCredentials) -> Iterator[Any]:
    """A raw connection under the evidence role.

    Deliberately raw: these rows test what **Postgres** refuses, so they must bypass every
    Python guard. A test that went through `PostgresEvidenceQuery` would be testing the
    Protocol's shape, which is defence #1 and already covered hermetically.
    """
    import pg8000.dbapi

    cred = evidence_credentials.fetch()
    conn = pg8000.dbapi.connect(
        host="127.0.0.1",
        port=5432,
        database="brieve",
        user=cred.username,
        password=cred.password,
    )
    yield conn
    try:
        conn.close()
    except Exception:
        pass


@pytest.fixture
def unique_correlation_id(request: pytest.FixtureRequest) -> str:
    """A distinct stream per test **per invocation**.

    Both halves matter, and 005 found each the hard way against Postgres while the
    in-memory provider stayed green: distinct per test or one row's leftover entries break
    another's chain assertions, and distinct per invocation or yesterday's run has already
    written the positions this one expects to start at.
    """
    return f"api-conformance-{request.node.name}-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def run_connection(run_credentials: VaultDatabaseCredentials) -> Any:
    """A factory for connections under the RUN role.

    The integrity check needs this rather than the evidence role: audit_stream_heads
    carries no grant for the read path at all, which is what stops it learning what it
    would need to forge.
    """
    import pg8000.dbapi

    def _open() -> Any:
        cred = run_credentials.fetch()
        return pg8000.dbapi.connect(
            host="127.0.0.1",
            port=5432,
            database="brieve",
            user=cred.username,
            password=cred.password,
        )

    return _open
