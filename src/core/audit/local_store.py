# SPDX-License-Identifier: Apache-2.0
"""Opening the platform's own evidence store under the run role.

Separate from the evidence read path on purpose. `audit_stream_heads` carries no grant for
the evidence role — a reader able to see the heads could learn what it would need to forge —
so anything that must read a head (integrity checking, reconciliation) needs the run role
instead, and needs somewhere to say so once.

In core rather than in either surface because both reach for it, and a helper owned by one
would make the other import across the surface boundary to open a database connection.
"""

from __future__ import annotations

from typing import Any

from core.durability.credentials import VaultDatabaseCredentials


def run_connection_factory(credentials: VaultDatabaseCredentials) -> Any:
    """A factory for connections under the **run** role."""
    import pg8000.dbapi

    def _open() -> Any:
        cred = credentials.fetch()
        return pg8000.dbapi.connect(
            host="127.0.0.1",
            port=5432,
            database="brieve",
            user=cred.username,
            password=cred.password,
        )

    return _open


__all__ = ["run_connection_factory"]
