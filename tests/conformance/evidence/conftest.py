# SPDX-License-Identifier: Apache-2.0
"""Two credentials, and the point of this lane is that they are different (015).

Every row here needs both: the platform's **shipping** credential, which can append to the
second copy and alter nothing there, and the collector **administrator's**, which can do
anything — including the tampering a row must arrange in order to prove it is detected.

**The platform must never hold the second one.** That is the whole of ADR-0055's
administrative boundary, and it is why these rows are `host_enclave`: the arranging has to
happen somewhere the platform's own workload identity cannot reach, which on this substrate
means the host. A row that held both credentials inside an allocation would be demonstrating
the comparator while quietly dissolving the separation it exists to check.

Every row file in this directory carries both markers::

    pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

`enclave` because the stack must be up; `host_enclave` because it cannot run inside
something the scheduler placed. The 013/014 lesson: a marker alone does not run a row that
no lane collects, and a lane alone does not skip a row that cannot run there.
"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import urllib.request
from collections.abc import Iterator
from typing import Any

import pg8000.dbapi
import pytest

#: Where `enclave-up` puts the platform's shipping credential. Read through Vault under an
#: operator token here, exactly as the mcp service reads it under its own attested identity —
#: the same path, a different way of being allowed to see it.
SHIPPER_CREDENTIAL_PATH = "secret/data/audit-egress/shipper"

#: The collector administrator's account. Held by the operator, never by the platform, and
#: never in the platform's Vault — a credential the platform's Vault stored would be one the
#: platform's administrators could retrieve, which is the capture this feature forecloses.
COLLECTOR_ADMIN_USER = "collector"
COLLECTOR_ADMIN_PASSWORD = "dev-only-collector-admin"
COLLECTOR_DB = "collector"
COLLECTOR_PORT = 5433


def _vault_read(path: str) -> dict[str, Any]:
    addr = (os.environ.get("VAULT_ADDR") or "https://127.0.0.1:8200").rstrip("/")
    token = os.environ.get("VAULT_TOKEN") or os.environ.get("VAULT_ROOT_TOKEN")
    if not token:
        pytest.fail(
            "no VAULT_TOKEN/VAULT_ROOT_TOKEN. `make conformance` passes it from .env; a bare "
            "pytest invocation needs it exported. Not skippable — a row that skips itself "
            "reports the same green as one that ran."
        )
    cacert = os.environ.get("VAULT_CACERT")
    context = ssl.create_default_context(cafile=cacert) if cacert else None
    request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
        f"{addr}/v1/{path}", headers={"X-Vault-Token": token}
    )
    with urllib.request.urlopen(request, timeout=10, context=context) as response:  # noqa: S310
        body = json.loads(response.read())
    data: dict[str, Any] = body["data"]["data"]
    return data


@pytest.fixture
def egress_configured() -> dict[str, Any]:
    """The shipping credential, or a loud failure naming what is missing.

    Not a skip. An estate without the second copy is one where tamper-evidence is ABSENT,
    which is a posture these rows assert elsewhere — but a row that skipped itself here
    would report the same green as one that verified the shipping actually works.
    """
    try:
        return _vault_read(SHIPPER_CREDENTIAL_PATH)
    except Exception as exc:  # noqa: BLE001 — the diagnosis is the value
        pytest.fail(
            f"the audit-egress shipping credential is not in Vault ({exc}). Run `make dev-up` "
            f"— its 'Second copy' step brings up the collector store and stores this."
        )


@pytest.fixture
def shipper_connection(egress_configured: dict[str, Any]) -> Iterator[Any]:
    """As the PLATFORM: append and read, and provably nothing more."""
    conn = pg8000.dbapi.connect(
        host=egress_configured["host"],
        port=int(egress_configured["port"]),
        database=egress_configured["dbname"],
        user=egress_configured["username"],
        password=egress_configured["password"],
    )
    conn.autocommit = True
    yield conn
    _close(conn)


@pytest.fixture
def collector_admin_connection() -> Iterator[Any]:
    """As the COLLECTOR ADMINISTRATOR: everything, including what the platform must not do.

    Used to read the second copy back independently, and to arrange the tampering a
    detection row has to detect. In a real deployment this is a different person's
    credential; here it is the same operator wearing the other hat, which the contract
    records under what these rows cannot prove.
    """
    conn = pg8000.dbapi.connect(
        host="127.0.0.1",
        port=COLLECTOR_PORT,
        database=COLLECTOR_DB,
        user=COLLECTOR_ADMIN_USER,
        password=COLLECTOR_ADMIN_PASSWORD,
    )
    conn.autocommit = True
    yield conn
    _close(conn)


@pytest.fixture
def platform_admin_connection() -> Iterator[Any]:
    """As the PLATFORM's database administrator — the threat actor these rows model.

    This is the credential that can rewrite the local trail and its head consistently, which
    is the attack ADR-0055 exists to make visible. Rows use it to *commit the attack*, then
    assert the second copy exposes it.
    """
    from tests.harness.operator_credentials import OperatorCredentials

    cred = OperatorCredentials().fetch()
    conn = pg8000.dbapi.connect(
        host="127.0.0.1",
        port=5432,
        database="brieve",
        user=cred.username,
        password=cred.password,
    )
    conn.autocommit = True
    yield conn
    _close(conn)


def query(conn: Any, sql: str, params: tuple[Any, ...] | None = None) -> list[Any]:
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params) if params else cursor.execute(sql)
        return [list(row) for row in cursor.fetchall()]
    finally:
        cursor.close()


def execute(conn: Any, sql: str, params: tuple[Any, ...] | None = None) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params) if params else cursor.execute(sql)
    finally:
        cursor.close()


def nomad(args: list[str]) -> str:
    return subprocess.run(["nomad", *args], capture_output=True, text=True).stdout


def _close(conn: Any) -> None:
    try:
        conn.close()
    except Exception:  # noqa: BLE001 — a close failure must not mask the row's own result
        pass
