# SPDX-License-Identifier: Apache-2.0
"""Portal sessions: an opaque id in a cookie, the token server-side, nothing persisted.

**In memory, deliberately not in Postgres.** FR-020b wants nothing persisted that could act
on a person's behalf later, and a session table is exactly that — a durable store of live
bearer tokens, which is the credential store this platform declines to operate. Losing
sessions when the portal restarts costs a re-login and loses nothing else: threads are in
the database, and SC-003 is about threads.

**The browser gets an opaque identifier and nothing else.** Not the token, not the subject,
not an expiry it could reason about. Everything the browser holds dies when the cookie is
cleared, and everything it could do with what it holds requires this process to still know
the id.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime

#: The cookie the browser carries. `__Host-` is not cosmetic: it forces Secure, forbids a
#: Domain attribute, and requires Path=/ — so the cookie cannot be scoped to a sibling
#: subdomain by anything that manages to set one.
COOKIE_NAME = "__Host-portal_session"

#: How long a session may live regardless of the token's own expiry.
#:
#: The token's `exp` is authoritative and is honoured first; this is the second bound, for
#: the case where a long-lived token would otherwise keep a forgotten browser tab live for
#: as long as the IdP allows.
MAX_SESSION_SECONDS = 12 * 60 * 60


@dataclass(frozen=True)
class Session:
    """What the portal knows about a logged-in person."""

    session_id: str
    subject_user_id: str
    tenant_id: str
    access_token: str
    expires_at: datetime
    created_at: datetime

    def is_live(self, *, now: datetime | None = None) -> bool:
        moment = now or datetime.now(UTC)
        if moment >= self.expires_at:
            return False
        return (moment - self.created_at).total_seconds() < MAX_SESSION_SECONDS

    def __repr__(self) -> str:  # pragma: no cover - defensive
        # Without this, a traceback or a debugger repr prints a live bearer token into a
        # log — the same reason `DatabaseCredential` redacts itself.
        return f"Session(session_id={self.session_id!r}, subject={self.subject_user_id!r})"


@dataclass
class SessionStore:
    """Opaque id → session. Nothing here outlives the process."""

    sessions: dict[str, Session] = field(default_factory=dict)

    def create(
        self,
        *,
        subject_user_id: str,
        tenant_id: str,
        access_token: str,
        expires_at: datetime,
    ) -> Session:
        self._sweep()
        # 32 bytes of urlsafe randomness. The id is the only thing standing between a
        # stolen cookie and a live token, so it is generated the way a token would be.
        session = Session(
            session_id=secrets.token_urlsafe(32),
            subject_user_id=subject_user_id,
            tenant_id=tenant_id,
            access_token=access_token,
            expires_at=expires_at,
            created_at=datetime.now(UTC),
        )
        self.sessions[session.session_id] = session
        return session

    def get(self, session_id: str | None) -> Session | None:
        """The live session for this id, or ``None``. Expired sessions are removed."""
        if not session_id:
            return None
        found = self.sessions.get(session_id)
        if found is None:
            return None
        if not found.is_live():
            del self.sessions[found.session_id]
            return None
        return found

    def destroy(self, session_id: str | None) -> None:
        if session_id:
            self.sessions.pop(session_id, None)

    def _sweep(self) -> None:
        for sid in [s for s, sess in self.sessions.items() if not sess.is_live()]:
            del self.sessions[sid]


def cookie_attributes() -> dict[str, object]:
    """How the session cookie is set. **Always Secure — there is no way to turn it off.**

    ``HttpOnly`` so no script can read it: the whole design rests on the browser being
    unable to extract anything usable. ``SameSite=Lax`` so a cross-site POST cannot ride
    the session, while an ordinary top-level navigation back from the IdP still carries it.

    **`Secure` is not configurable, and the `__Host-` prefix is why.** That prefix requires
    Secure, forbids a Domain attribute, and requires Path=/ — so a browser *rejects the
    cookie outright* if Secure is absent, and the portal silently cannot log anyone in.
    An earlier version took a `secure=False` parameter for dev over plain HTTP; the
    accessibility gate found it immediately, because a real browser did what the test
    client had not.

    Dev over loopback works anyway: browsers treat `http://localhost` and `http://127.0.0.1`
    as trustworthy origins, so a Secure cookie is accepted there. That was already the
    claim in this docstring — the flag contradicted it, and removing the flag is what makes
    it true. A flag whose wrong value is invisible until it matters should not exist.
    """
    return {"httponly": True, "secure": True, "samesite": "lax", "path": "/"}


__all__ = [
    "COOKIE_NAME",
    "MAX_SESSION_SECONDS",
    "Session",
    "SessionStore",
    "cookie_attributes",
]
