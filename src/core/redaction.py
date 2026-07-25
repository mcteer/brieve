# SPDX-License-Identifier: Apache-2.0
"""Redact secret-bearing values from audit/span payloads."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any


def redact_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Return argument keys and content hashes — never raw values."""
    hashes: dict[str, str] = {}
    for key, value in arguments.items():
        digest = hashlib.sha256(repr(value).encode("utf-8")).hexdigest()
        hashes[str(key)] = digest
    return {
        "argument_keys": sorted(str(k) for k in arguments),
        "argument_hashes": hashes,
    }


def safe_error_code(exc: BaseException) -> str:
    """Stable error code without exception message content."""
    return type(exc).__name__
