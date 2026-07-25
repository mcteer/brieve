# SPDX-License-Identifier: Apache-2.0
"""Obvious fixture markers for secret-leak assertions — not plausible real secrets."""

# Deliberately absurd markers so scanners and helpers can detect leaks without
# embedding credential-shaped strings in the repository.
SECRET_MARKER = "HARNESS_FIXTURE_SECRET_MARKER_NOT_A_REAL_SECRET"
BROKERED_GRAIN_MARKER = "HARNESS_FIXTURE_BROKERED_GRAIN_MARKER_NOT_A_REAL_SECRET"
AUTHORITY_SECRET_MARKER = "HARNESS_FIXTURE_AUTHORITY_SECRET_MARKER_NOT_A_REAL_SECRET"
SECRET_MARKERS: tuple[str, ...] = (
    SECRET_MARKER,
    BROKERED_GRAIN_MARKER,
    AUTHORITY_SECRET_MARKER,
)
