# SPDX-License-Identifier: Apache-2.0
"""Obvious fixture markers for secret-leak assertions — not plausible real secrets."""

# Deliberately absurd markers so scanners and helpers can detect leaks without
# embedding credential-shaped strings in the repository.
SECRET_MARKER = "HARNESS_FIXTURE_SECRET_MARKER_NOT_A_REAL_SECRET"
BROKERED_GRAIN_MARKER = "HARNESS_FIXTURE_BROKERED_GRAIN_MARKER_NOT_A_REAL_SECRET"
AUTHORITY_SECRET_MARKER = "HARNESS_FIXTURE_AUTHORITY_SECRET_MARKER_NOT_A_REAL_SECRET"
#: 038's authoring must-deny cases. A credential a GENERATOR COULD REACH is what those cases
#: need — a subject that never contains one is the passing stub ADR-0047 forbids — and the
#: marker below is reachable in exactly the way that matters: it sits in a subject file the
#: agent reads, and the assertion is that it does not come out the other side.
#:
#: **Absurd rather than plausible, and the first attempt got this wrong.** A cloud-access-key-shaped
#: literal was written into the 038 fixtures and the gitleaks lane caught it on the first CI
#: run. A credential-shaped string in the repository is a finding whether or not it
#: is real, because every scanner that will ever run over this tree has to decide, and "it was
#: only a fixture" is a thing you learn after the alert.
AUTHORING_SUBJECT_SECRET_MARKER = "HARNESS_FIXTURE_AUTHORING_SUBJECT_SECRET_NOT_A_REAL_SECRET"

SECRET_MARKERS: tuple[str, ...] = (
    SECRET_MARKER,
    BROKERED_GRAIN_MARKER,
    AUTHORITY_SECRET_MARKER,
    AUTHORING_SUBJECT_SECRET_MARKER,
)
