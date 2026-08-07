# SPDX-License-Identifier: Apache-2.0
"""Endorsed content in the enclave database (045, T005).

Mirrors `core.answering.conversations.postgres` in discipline — brokered credential per
connection, one `_run` wrapper that turns any driver failure into one named error, idempotent
`migrate()` that `SET ROLE`s first — and shares no table with it.

**The store never decides what may be cited.** It reads and writes versions; whether a version
is the one answers rest on is the governance record's business, in `authority`. Keeping the
decision out of here is what stops "which content" and "may we trust it" from becoming one
question with one place to get it wrong.
"""

from __future__ import annotations

import pathlib
from datetime import UTC, datetime
from typing import Any

from core.answering.endorsed.records import (
    ADOPTED,
    CANDIDATE,
    SUPERSEDED,
    EndorsedDocument,
    SyncedVersion,
    digest_of_document,
)

SCHEMA_PATH = pathlib.Path(__file__).with_name("schema.sql")


class EndorsedStoreError(RuntimeError):
    """The endorsed store could not be reached or read.

    **Raised, never degraded to empty.** Empty means "this customer has endorsed nothing", and
    an outage presenting as that would make answers quietly stop citing material the customer
    believes is trusted — the platform appearing to have forgotten the documents rather than
    appearing to be down. Same line `CorpusUnavailable` draws for the pinned side.
    """


class DigestMismatch(EndorsedStoreError):
    """Stored content does not match the digest the version recorded for it (FR-007).

    A refusal, never a fallback. A citation into content that changed underneath its pin reads
    as evidence for something nobody endorsed.
    """


def _aware(stamp: Any) -> datetime:
    if isinstance(stamp, datetime):
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    return datetime.now(UTC)


class PostgresEndorsedStore:
    """Synced versions of endorsed customer content."""

    def __init__(
        self,
        *,
        credentials: Any,
        host: str = "127.0.0.1",
        port: int = 5432,
        dbname: str = "brieve",
    ) -> None:
        self._credentials = credentials
        self._host = host
        self._port = port
        self._dbname = dbname

    def _connect(self) -> Any:
        import pg8000.dbapi

        cred = self._credentials.fetch()
        return pg8000.dbapi.connect(
            host=self._host,
            port=self._port,
            database=self._dbname,
            user=cred.username,
            password=cred.password,
        )

    def _run(self, work: Any) -> Any:
        conn = None
        try:
            conn = self._connect()
            return work(conn)
        except EndorsedStoreError:
            raise
        except Exception as exc:
            raise EndorsedStoreError(
                f"endorsed content store unavailable: {type(exc).__name__}: {exc}"
            ) from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001 — a close failure must not mask the real one
                    pass

    def migrate(self) -> None:
        """Apply the schema as the shared login role, so the next credential can still alter it.

        The `SET ROLE` is not defensive style — it is the fix for a measured crash loop. Vault
        issues a fresh Postgres user per credential, so tables created under one allocation are
        owned by a user the next allocation is not; `CREATE TABLE IF NOT EXISTS` then no-ops
        while `CREATE INDEX IF NOT EXISTS` needs ownership, and every later start dies with
        `must be owner of table`.
        """

        def work(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute(
                "SELECT r.rolname FROM pg_auth_members m "
                "JOIN pg_roles r ON r.oid = m.roleid "
                "JOIN pg_roles me ON me.oid = m.member "
                "WHERE me.rolname = current_user AND r.rolcanlogin LIMIT 1"
            )
            row = cur.fetchone()
            if row:
                cur.execute(f'SET ROLE "{row[0]}"')
            cur.execute(SCHEMA_PATH.read_text())
            conn.commit()

        self._run(work)

    def write_version(self, version: SyncedVersion) -> None:
        """Write one sync. **Insert-only** — a version that exists is never rewritten.

        A repeated sync that finds the upstream unchanged produces the same `version_id`, so
        this no-ops rather than conflicting. That is the immutability the pin depends on:
        "the same identity means the same content" has to hold in both directions.
        """

        def work(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO endorsed_versions (version_id, tenant_id, source, upstream_tip, "
                "synced_at, synced_by, state, document_count) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (version_id) DO NOTHING",
                (
                    version.version_id,
                    version.tenant_id,
                    version.source,
                    version.upstream_tip,
                    version.synced_at,
                    version.synced_by,
                    version.state,
                    len(version.documents),
                ),
            )
            for path, document in version.documents.items():
                cur.execute(
                    "INSERT INTO endorsed_documents (version_id, path, url, digest) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT (version_id, path) DO NOTHING",
                    (version.version_id, path, document.url, document.digest),
                )
                for anchor, body in document.sections.items():
                    cur.execute(
                        "INSERT INTO endorsed_sections (version_id, path, anchor, body) "
                        "VALUES (%s, %s, %s, %s) "
                        "ON CONFLICT (version_id, path, anchor) DO NOTHING",
                        (version.version_id, path, anchor, body),
                    )
            conn.commit()

        self._run(work)

    def read_version(self, version_id: str, *, verify: bool = True) -> SyncedVersion | None:
        """One version with its documents, digest-verified.

        `verify` defaults to on and every production caller leaves it on. It exists as a
        parameter only so a row can construct the mismatch it wants to assert about — the same
        posture `load_corpus` takes, and for the same reason: a verification nothing can
        exercise is a verification nobody knows works.
        """

        def work(conn: Any) -> SyncedVersion | None:
            cur = conn.cursor()
            cur.execute(
                "SELECT tenant_id, source, upstream_tip, synced_at, synced_by, state "
                "FROM endorsed_versions WHERE version_id = %s",
                (version_id,),
            )
            head = cur.fetchone()
            if head is None:
                return None

            cur.execute(
                "SELECT path, url, digest FROM endorsed_documents WHERE version_id = %s",
                (version_id,),
            )
            documents_meta = {row[0]: (row[1], row[2]) for row in cur.fetchall()}

            cur.execute(
                "SELECT path, anchor, body FROM endorsed_sections WHERE version_id = %s",
                (version_id,),
            )
            sections: dict[str, dict[str, str]] = {}
            for path, anchor, body in cur.fetchall():
                sections.setdefault(path, {})[anchor] = body

            documents: dict[str, EndorsedDocument] = {}
            for path, (url, digest) in documents_meta.items():
                body = sections.get(path, {})
                if verify and digest_of_document(body) != digest:
                    raise DigestMismatch(
                        f"{path} in version {version_id} does not match the digest recorded "
                        f"when it was synced. The content changed underneath its pin, so a "
                        f"citation into it would resolve to something other than what was "
                        f"endorsed — this refuses rather than answering from it."
                    )
                documents[path] = EndorsedDocument(
                    path=path,
                    url=url,
                    digest=digest,
                    anchors=frozenset(body),
                    sections=dict(body),
                )

            return SyncedVersion(
                version_id=version_id,
                tenant_id=head[0],
                source=head[1],
                upstream_tip=head[2],
                synced_at=_aware(head[3]),
                synced_by=head[4],
                state=head[5],
                documents=documents,
            )

        result: SyncedVersion | None = self._run(work)
        return result

    def latest_candidate(self, *, tenant_id: str, source: str) -> str | None:
        """The newest candidate for a source, which is what a review is read against."""

        def work(conn: Any) -> str | None:
            cur = conn.cursor()
            cur.execute(
                "SELECT version_id FROM endorsed_versions WHERE tenant_id = %s AND source = %s "
                "AND state = %s ORDER BY synced_at DESC LIMIT 1",
                (tenant_id, source, CANDIDATE),
            )
            row = cur.fetchone()
            return str(row[0]) if row else None

        result: str | None = self._run(work)
        return result

    def adopted_tip(self, *, tenant_id: str, source: str) -> str | None:
        """What the source's adopted version recorded as upstream — detection's left-hand side."""

        def work(conn: Any) -> str | None:
            cur = conn.cursor()
            cur.execute(
                "SELECT upstream_tip FROM endorsed_versions WHERE tenant_id = %s "
                "AND source = %s AND state = %s ORDER BY synced_at DESC LIMIT 1",
                (tenant_id, source, ADOPTED),
            )
            row = cur.fetchone()
            return str(row[0]) if row else None

        result: str | None = self._run(work)
        return result

    def mark_adopted(self, *, tenant_id: str, source: str, version_id: str) -> None:
        """Flip a candidate to adopted and supersede the previous one. **Nothing is deleted.**

        Superseding rather than deleting is what makes US4 possible: a run that pinned the old
        version keeps reading it, and its record keeps naming something that exists. Retention
        is deferred with its reasoning (R3) rather than expiring on a timer nobody chose.

        The content is untouched — this moves a label. The governance record's
        `adopted_version` is the authority on what answers rest on; this keeps the store's own
        view consistent with it so `adopted_tip` can answer detection without asking the fabric.
        """

        def work(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute(
                "UPDATE endorsed_versions SET state = %s WHERE tenant_id = %s AND source = %s "
                "AND state = %s AND version_id <> %s",
                (SUPERSEDED, tenant_id, source, ADOPTED, version_id),
            )
            cur.execute(
                "UPDATE endorsed_versions SET state = %s WHERE version_id = %s",
                (ADOPTED, version_id),
            )
            conn.commit()

        self._run(work)
