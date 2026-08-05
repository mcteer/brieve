# SPDX-License-Identifier: Apache-2.0
"""Obvious fixture markers for secret-leak assertions — not plausible real secrets."""

# Deliberately absurd markers so scanners and helpers can detect leaks without
# embedding credential-shaped strings in the repository.
SECRET_MARKER = "HARNESS_FIXTURE_SECRET_MARKER_NOT_A_REAL_SECRET"
BROKERED_GRAIN_MARKER = "HARNESS_FIXTURE_BROKERED_GRAIN_MARKER_NOT_A_REAL_SECRET"
AUTHORITY_SECRET_MARKER = "HARNESS_FIXTURE_AUTHORITY_SECRET_MARKER_NOT_A_REAL_SECRET"
#: 038's authoring must-deny cases. Absurd rather than plausible, like the three above: a
#: credential-shaped string in the repository is a scanner finding whether or not it is real,
#: and what those cases need is a secret the agent can REACH rather than one that looks real.
AUTHORING_SUBJECT_SECRET_MARKER = "HARNESS_FIXTURE_AUTHORING_SUBJECT_SECRET_NOT_A_REAL_SECRET"

SECRET_MARKERS: tuple[str, ...] = (
    SECRET_MARKER,
    BROKERED_GRAIN_MARKER,
    AUTHORITY_SECRET_MARKER,
    AUTHORING_SUBJECT_SECRET_MARKER,
)
