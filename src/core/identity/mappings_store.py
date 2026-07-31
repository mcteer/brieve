# SPDX-License-Identifier: Apache-2.0
"""Reading claim-to-role mappings back out of the trust fabric.

`claims.py` defines what a mapping IS and `authority_submit.py` gets one written under
quorum. Between them the loop was open: nothing read the approved mappings, so the
verifier was constructed with none and `resolve_roles` returned empty for every token.
Empty means refuse — correctly, and by design — so the production API refused every
authenticated request no matter which identity provider it was pointed at.

**One record per mapping, not one record holding all of them.** A single record would
have to be read-modify-written to add a mapping, and a gated write cannot do that
safely: the new value is computed from a base that may be several approvals stale by
the time quorum lands, so the later write silently drops the earlier one. Approving a
mapping would then sometimes revoke a different one, which is the failure a quorum gate
exists to prevent rather than to cause. Separate records also make each mapping
independently approvable and independently revocable, which is what an operator
reviewing a Control Group request is actually being asked to decide about.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from typing import Any, Protocol

from core.errors import CoreError
from core.identity.claims import ClaimMapping

#: Long enough that a token check is not a Vault round trip, short enough that an
#: approved mapping takes effect on its own. Revocation is the binding constraint:
#: this is the window in which a removed mapping still grants its role.
DEFAULT_MAPPING_TTL_SECONDS = 60.0

_UNSAFE = re.compile(r"[^a-z0-9]+")


class ClaimMappingsUnavailable(CoreError):
    """The mappings could not be read. Refuse — do not proceed with none.

    The distinction this exists to preserve: an empty mapping set and an unreadable one
    both resolve every token to no roles, but the first is a deployment that has granted
    nobody anything and the second is an outage. Collapsing them sends whoever
    investigates to look at claim configuration during a Vault incident.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.reason_code = "claim_mappings_unavailable"


def mapping_key(mapping: ClaimMapping) -> str:
    """The record name for this mapping — stable, unique, and readable enough to scan.

    Derived rather than chosen so that re-submitting an identical mapping targets the
    record it already occupies. A generated name would accumulate a fresh copy per
    submission, and revoking the mapping would then mean finding all of them.

    The digest carries uniqueness because `claim_name` is routinely a URI — Auth0 and
    every other provider that namespaces custom claims emit `https://example/roles`,
    whose slashes would silently nest the record under a folder that nothing lists.
    The role prefix is there only so an operator listing the path can see what a record
    is about without reading it.
    """
    digest = hashlib.sha256(
        "\x00".join((mapping.claim_name, mapping.claim_value, mapping.role)).encode()
    ).hexdigest()[:16]
    readable = _UNSAFE.sub("-", mapping.role.lower()).strip("-") or "role"
    return f"{readable}-{digest}"


class _PathReader(Protocol):
    """The slice of `VaultDatabaseCredentials` this needs, and nothing more."""

    def read_path(self, path: str, *, token: str | None = None) -> dict[str, Any] | None: ...

    def list_path(self, path: str, *, token: str | None = None) -> list[str] | None: ...


class VaultClaimMappings:
    """Reads the approved claim-to-role mappings, as an attested workload.

    Callable, so it drops straight into `TokenVerifier(mappings_source=...)`.
    """

    def __init__(
        self,
        *,
        credentials: _PathReader,
        data_path: str,
        metadata_path: str | None = None,
        ttl_seconds: float = DEFAULT_MAPPING_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._credentials = credentials
        self._data_path = data_path.strip("/")
        # KV v2 splits reads from listing: data lives under `data/`, keys under
        # `metadata/`. Deriving it rather than asking for both keeps a caller from
        # configuring a metadata path that points at a different secret than the data
        # path — which would list one set of mappings and read another.
        self._metadata_path = (metadata_path or _as_metadata(self._data_path)).strip("/")
        self._ttl = ttl_seconds
        self._clock = clock
        self._cached: list[ClaimMapping] | None = None
        self._fetched_at: float | None = None

    def __call__(self) -> list[ClaimMapping]:
        return self.current()

    def current(self) -> list[ClaimMapping]:
        """The approved mappings, from cache when fresh.

        Fails closed when the cache has expired and the fabric cannot be reached, rather
        than serving the stale set — the same choice `_KeyCache` makes for signing keys
        one module over, and for the same reason. A mapping that survived its revocation
        because the fabric was briefly unreachable is a grant nobody approved.
        """
        if self._cached is not None and self._fetched_at is not None:
            if (self._clock() - self._fetched_at) < self._ttl:
                return self._cached

        mappings = self._load()
        self._cached = mappings
        self._fetched_at = self._clock()
        return mappings

    def _load(self) -> list[ClaimMapping]:
        try:
            keys = self._credentials.list_path(self._metadata_path)
        except Exception as exc:  # noqa: BLE001 — an unlistable path must not read as empty
            raise ClaimMappingsUnavailable(
                f"claim mappings could not be listed at {self._metadata_path!r}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

        # A folder that is not there is a deployment which has approved no mappings. That
        # is a legitimate state — a fresh estate — and it refuses every token, which is
        # the right answer for an estate that has granted nobody anything.
        if not keys:
            return []

        mappings: list[ClaimMapping] = []
        for key in sorted(keys):
            if key.endswith("/"):
                # A nested folder, which nothing here writes. Skipping it rather than
                # reading it keeps a stray subtree from becoming a silent grant.
                continue
            mappings.append(self._read_one(key))
        return mappings

    def _read_one(self, key: str) -> ClaimMapping:
        path = f"{self._data_path}/{key}"
        try:
            response = self._credentials.read_path(path)
        except Exception as exc:  # noqa: BLE001 — see ClaimMappingsUnavailable
            raise ClaimMappingsUnavailable(
                f"claim mapping {key!r} could not be read: {type(exc).__name__}: {exc}"
            ) from exc

        record = ((response or {}).get("data") or {}).get("data")
        if not isinstance(record, dict):
            # Listed but unreadable. NOT skipped: a record that vanished between the list
            # and the read is a fabric that is changing underneath us, and quietly
            # dropping it would resolve a token against a partial mapping set — a subset
            # of approved grants, presented as the whole.
            raise ClaimMappingsUnavailable(f"claim mapping {key!r} is listed but carries no record")

        try:
            return ClaimMapping(
                claim_name=str(record["claim_name"]),
                claim_value=str(record["claim_value"]),
                role=str(record["role"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            # Same reasoning as above, one level down. A malformed record is refused
            # rather than skipped, because "we could not understand one of your approved
            # grants" must not present as "that grant does not exist".
            raise ClaimMappingsUnavailable(
                f"claim mapping {key!r} is malformed: {type(exc).__name__}"
            ) from exc


def _as_metadata(data_path: str) -> str:
    """`mount/data/prefix` -> `mount/metadata/prefix`."""
    parts = data_path.split("/")
    for index, part in enumerate(parts):
        if part == "data":
            return "/".join([*parts[:index], "metadata", *parts[index + 1 :]])
    # No `data/` segment: either a KV v1 mount or a caller that passed the mount root.
    # Returning it unchanged lets LIST answer for KV v1 and 404 -> "no mappings" for the
    # mistake, which is visible in the refusal reason rather than silently wrong.
    return data_path


__all__ = [
    "DEFAULT_MAPPING_TTL_SECONDS",
    "ClaimMappingsUnavailable",
    "VaultClaimMappings",
    "mapping_key",
]
