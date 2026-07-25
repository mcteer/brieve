# SPDX-License-Identifier: Apache-2.0
"""Typed authority refuse/deny errors."""

from __future__ import annotations

from core.errors import CoreError


class AuthorityRefuseError(CoreError):
    """Run start refused — no usable task credential issued."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str = "authority_refused",
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, correlation_id=correlation_id)
        self.reason_code = reason_code


class AuthorityExpiredError(CoreError):
    """Task credential past TTL."""

    def __init__(
        self,
        message: str = "task authority expired",
        *,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, correlation_id=correlation_id)
        self.reason_code = "authority_expired"


class AuditAppendFailed(CoreError):
    """Audit append failed on an authority/mirroring enforcement path."""

    def __init__(
        self,
        message: str = "audit append failed",
        *,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, correlation_id=correlation_id)
