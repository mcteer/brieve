# SPDX-License-Identifier: Apache-2.0
"""Per-run salted content hashes for authority-related audit payloads."""

from __future__ import annotations

import hashlib
import hmac


def content_hash(run_salt: bytes, material: bytes | str) -> str:
    """Return HMAC-SHA256(run_salt, material) as lowercase hex digest."""
    if isinstance(material, str):
        data = material.encode("utf-8")
    else:
        data = material
    return hmac.new(run_salt, data, hashlib.sha256).hexdigest()
