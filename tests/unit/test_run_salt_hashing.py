# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — per-run salted HMAC hashes."""

from __future__ import annotations

import secrets

from tests.harness.secrets import AUTHORITY_SECRET_MARKER

from core.authority.hashing import content_hash


def test_content_hash_is_hmac_hex_and_hides_raw() -> None:
    salt = secrets.token_bytes(32)
    digest = content_hash(salt, AUTHORITY_SECRET_MARKER)
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    assert AUTHORITY_SECRET_MARKER not in digest
    assert content_hash(salt, AUTHORITY_SECRET_MARKER) == digest
    assert content_hash(secrets.token_bytes(32), AUTHORITY_SECRET_MARKER) != digest
