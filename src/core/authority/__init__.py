# SPDX-License-Identifier: Apache-2.0
"""Per-task authority manufacture and types."""

from core.authority.clock import Clock, SystemClock
from core.authority.errors import AuditAppendFailed, AuthorityExpiredError, AuthorityRefuseError
from core.authority.hashing import content_hash
from core.authority.intersection import intersect_scopes, live_effective
from core.authority.manufacture import ManufacturedAuthority, manufacture_authority
from core.authority.types import AuthorityScope, TaskCredentialRef

__all__ = [
    "AuditAppendFailed",
    "AuthorityExpiredError",
    "AuthorityRefuseError",
    "AuthorityScope",
    "Clock",
    "ManufacturedAuthority",
    "SystemClock",
    "TaskCredentialRef",
    "content_hash",
    "intersect_scopes",
    "live_effective",
    "manufacture_authority",
]
