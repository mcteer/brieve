# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — what the scrub takes and what it leaves (052, T010-T015, A1-A3, A6-A8).

041's FR-033 closed one of the two places a customer's authored content rests in the control
plane. This is the function that closes the other.

**The rows that matter most are the ones about what SURVIVES.** Retention and attestation only
avoid trading against each other because `provenance` already carries a path-and-digest line per
authored file — so a reviewer can hash a merged pull request and match it against what the run
recorded proposing, with the platform holding none of the content. A scrub that took that field
would satisfy every retention row here, destroy US2, and look like a tidier implementation while
doing it.
"""

from __future__ import annotations

from typing import Any

import pytest
from tests.fixtures.authoring_payloads import (
    FILES,
    PROVENANCE,
    authored_payload,
    empty_payload,
    scrubbed_payload,
)
from tests.harness.secrets import AUTHORING_SUBJECT_SECRET_MARKER

from core.authoring.retention import (
    CONTENT_BEARING_PROPOSAL_FIELDS,
    SCRUBBED_MARKER,
    scrub_proposal_payload,
)

#: Keys that are prose *about* the change rather than extracts *from* it. All must survive.
KEPT_SCALARS = ("title", "task", "target_repository", "branch", "state")


def _scrub(payload: dict[str, Any] | None = None) -> tuple[dict[str, Any], int]:
    return scrub_proposal_payload(payload if payload is not None else authored_payload())


def test_the_whole_payload_matches_the_expected_shape() -> None:
    """Diffed whole, not key by key.

    A field-by-field assertion passes while quietly ignoring a key nobody thought to name.
    Comparing against the expected fixture catches a scrub that took something extra.
    """
    out, _ = _scrub()
    assert out == scrubbed_payload()


def test_every_body_is_cleared_and_the_count_says_how_many() -> None:
    """Row A1. The count is the assertion — otherwise "nothing" and "everything" look alike."""
    out, cleared = _scrub()
    assert cleared == len(FILES)
    assert all(f["body"] == "" for f in out["authoring_proposal"]["files"])


def test_the_model_authored_prose_is_cleared() -> None:
    """Row A1. Both fields quote the subject and both travel in the pull request body.

    `usage` joined `rationale` at implementation: the first acceptance sweep after the backfill
    found one carrying a shell transcript with a credential-shaped assignment. The spec's
    "prose about the change, not an extract from it" distinction did not survive a real payload.
    """
    out, _ = _scrub()
    proposal = out["authoring_proposal"]
    assert proposal["rationale"] == ""
    assert proposal["usage"] == ""
    assert CONTENT_BEARING_PROPOSAL_FIELDS == {"rationale", "usage"}


def test_a_credential_shaped_line_in_usage_does_not_survive() -> None:
    """The specific finding, named so the regression is recognisable if it returns."""
    assert "VAULT_TOKEN" in str(authored_payload())
    out, _ = _scrub()
    assert "VAULT_TOKEN" not in str(out)


def test_the_subject_marker_is_gone_from_the_whole_payload() -> None:
    """The property a store sweep will assert, checked here where it is cheap.

    The fixture's bodies and rationale carry the harness marker, so its absence from the
    rendered payload is evidence rather than an absence of nothing.
    """
    before = authored_payload()
    assert AUTHORING_SUBJECT_SECRET_MARKER in str(before)
    out, _ = _scrub(before)
    assert AUTHORING_SUBJECT_SECRET_MARKER not in str(out)


@pytest.mark.parametrize("key", KEPT_SCALARS)
def test_prose_about_the_change_survives(key: str) -> None:
    """Row A2. A reviewer reading a scrubbed run still learns what was proposed."""
    out, _ = _scrub()
    assert out["authoring_proposal"][key] == authored_payload()["authoring_proposal"][key]


def test_paths_and_diff_flags_survive() -> None:
    """Row A2. Which files were touched, and whether each was created or edited."""
    out, _ = _scrub()
    kept = [(f["path"], f["is_diff"]) for f in out["authoring_proposal"]["files"]]
    assert kept == [(path, is_diff) for path, _, is_diff in FILES]


def test_provenance_survives_intact() -> None:
    """ROW A3 — US2's single point of failure, asserted by name.

    Every other kept field is convenience. This one is why a scrub is defensible at all: a
    reviewer can hash the merged pull request and match it against what the run recorded
    proposing, without the platform holding the content.
    """
    out, _ = _scrub()
    assert out["authoring_proposal"]["provenance"] == PROVENANCE


def test_every_authored_path_still_has_a_digest_line() -> None:
    """Row A3's second half. The list surviving is not enough — it must still resolve.

    A change that kept `provenance` but dropped the per-file lines would pass the row above and
    leave a reviewer unable to prove anything.
    """
    out, _ = _scrub()
    proposal = out["authoring_proposal"]
    lines = "\n".join(proposal["provenance"])
    for entry in proposal["files"]:
        assert f"`{entry['path']}` — `" in lines, entry["path"]


def test_cleared_keys_are_emptied_not_removed() -> None:
    """Row A6. A reader distinguishing absent from emptied treats a scrubbed run as malformed."""
    out, _ = _scrub()
    proposal = out["authoring_proposal"]
    assert "rationale" in proposal
    assert all("body" in f for f in proposal["files"])


def test_the_scrubbed_marker_is_set() -> None:
    """What lets `proposal_from_payload` refuse, and tells an auditor why bodies are empty."""
    out, _ = _scrub()
    assert out["authoring_proposal"][SCRUBBED_MARKER] is True
    assert SCRUBBED_MARKER not in authored_payload()["authoring_proposal"]


def test_a_run_that_authored_nothing_scrubs_cleanly() -> None:
    """Row A7. A successful run and an empty one must not take different cleanup paths."""
    out, cleared = _scrub(empty_payload())
    assert cleared == 0
    assert out == empty_payload()


def test_scrubbing_twice_changes_nothing() -> None:
    """Row A8. Terminal state can be reached more than once."""
    once, first = _scrub()
    twice, second = scrub_proposal_payload(once)
    assert first == len(FILES)
    assert second == 0
    assert twice == once


def test_the_input_is_not_mutated() -> None:
    """Pure means pure. A caller that still holds the original must still hold the content."""
    payload = authored_payload()
    _scrub(payload)
    assert payload["authoring_proposal"]["files"][0]["body"] != ""
    assert payload["authoring_proposal"]["rationale"] != ""
    assert payload["authoring_proposal"]["usage"] != ""


def test_a_payload_with_no_proposal_key_is_returned_unchanged() -> None:
    """Not every checkpoint is an authoring one, and the scrub must be safe on all of them."""
    other: dict[str, Any] = {"propose_progress": {"phases": []}, "__run_result__": {"tools": []}}
    out, cleared = scrub_proposal_payload(other)
    assert cleared == 0
    assert out == other
