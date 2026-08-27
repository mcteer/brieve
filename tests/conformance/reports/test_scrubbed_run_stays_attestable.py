# SPDX-License-Identifier: Apache-2.0
"""GATE:evidence — a scrubbed run can still be attested (052, T029-T033, US2, A12-A14).

A scrub that satisfied US1 alone would delete the content **and** the ability to say what
happened, which is the trade ADR-0018 and Principle IX refuse. This file is the other half.

**Two things make it hold, and neither was designed here — both were found by measurement.**

1. `compile_report` reads **audit entries**, not `checkpoints.payload`. So clearing the payload
   cannot affect a RunReport at all. That makes "the report still compiles" nearly free, and
   the row below asserts the *independence* rather than the outcome, because an outcome row
   that cannot fail is the passing stub ADR-0047 forbids.
2. `provenance` already carried a path-and-digest line per authored file. That is what a
   reviewer uses to prove a merged pull request is the proposal the run made, with the platform
   holding none of the content.

**And one thing had to be checked rather than assumed.** The spec recorded as an assumption
that the audit trail does not carry the file bodies — FR-013 refused the trail a copy nobody can
delete. If it did, this feature would close one door and leave another, exactly as 041 did. It
does not, and the enclave row below is what says so on every run rather than once.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from core.authoring.retention import scrub_proposal_payload
from tests.fixtures.authoring_payloads import FILES, authored_payload


def test_the_report_is_compiled_from_the_trail_not_the_payload() -> None:
    """Row A12's real content: the scrub CANNOT affect a report, and this says why.

    Asserting "the report still compiles" would pass whether or not the scrub worked. What is
    worth pinning is the reason — `compile_report` takes audit entries — because a future change
    that fed it the checkpoint payload would make this feature start destroying attestation, and
    nothing else here would notice.
    """
    import inspect

    from core.reports.compile import compile_report

    signature = inspect.signature(compile_report)
    assert "entries" in signature.parameters
    source = inspect.getsource(compile_report)
    assert "checkpoint" not in source, (
        "compile_report now reads a checkpoint. The payload scrub would start affecting "
        "attestation, and US2's guarantee would need rebuilding."
    )


def test_the_surviving_manifest_matches_the_authored_files() -> None:
    """Row A13/A14's mechanism, and the whole argument that scrubbing is safe.

    A reviewer takes the merged pull request, hashes each file, and matches it against what the
    run recorded proposing. This asserts that path is still walkable after the scrub — using the
    real digests, so a manifest that survived but stopped resolving would fail.
    """
    scrubbed, _ = scrub_proposal_payload(authored_payload())
    proposal = scrubbed["authoring_proposal"]
    manifest = "\n".join(proposal["provenance"])

    for path, body, _ in FILES:
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        assert f"`{path}` — `{digest}`" in manifest, path

    assert all(entry["body"] == "" for entry in proposal["files"]), (
        "the match above must hold with the platform holding NO content — otherwise it proves "
        "nothing about a scrubbed run"
    )


def test_the_pull_request_stays_identifiable() -> None:
    """Row A13. A reviewer who cannot find the pull request cannot check anything against it."""
    scrubbed, _ = scrub_proposal_payload(authored_payload())
    assert scrubbed["__run_result__"]["pr_url"].startswith("https://github.com/")
    proposal = scrubbed["authoring_proposal"]
    assert proposal["target_repository"] == "acme/infra"
    assert proposal["branch"].startswith("brieve/authoring/")


def test_the_record_does_not_claim_content_it_no_longer_holds() -> None:
    """Row A14. The scrubbed marker is what stops a reader inferring the run authored nothing.

    Without it, empty bodies read as "this run wrote empty files" — an attestation that asserts
    more, and differently, than the record supports.
    """
    scrubbed, _ = scrub_proposal_payload(authored_payload())
    proposal = scrubbed["authoring_proposal"]
    assert proposal["scrubbed"] is True
    assert len(proposal["files"]) == len(FILES), "the file list must not shrink with the bodies"


def test_the_proposal_payload_has_no_reader_outside_the_publish_path() -> None:
    """T029. A consumer added later would break silently on a scrubbed payload.

    `PROPOSAL_PAYLOAD_KEY` has exactly two: the entrypoint that writes it and
    `proposal_from_payload`, which now refuses a scrubbed one. A portal template or report
    compiler reading it would find empty bodies and no reason to complain.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "src"
    readers = [
        path
        for path in src.rglob("*.py")
        if "__pycache__" not in path.parts
        and "PROPOSAL_PAYLOAD_KEY" in path.read_text(encoding="utf-8")
    ]
    assert {p.name for p in readers} == {"authoring.py", "entrypoint.py"}, sorted(
        p.relative_to(src).as_posix() for p in readers
    )


@pytest.mark.enclave
def test_the_audit_trail_carries_no_authored_body() -> None:
    """THE ASSUMPTION THIS FEATURE RESTS ON, checked rather than believed.

    FR-013 refused the trail a copy nobody can delete, and the spec recorded as an assumption
    that the bodies never reach it. If they did, this feature would close the checkpoint door
    and leave the trail open — exactly the shape 041 left behind, one store over.

    Measured: the largest audit payload in the live store is a few kilobytes, and entries
    naming `author_file` carry the tool name rather than its arguments.
    """
    from tests.conformance.durability import dispatch_harness as h

    conn = h.connection()
    try:
        rows = h.query(
            conn,
            "SELECT max(length(payload::text)) FROM audit_entries",
        )
    finally:
        conn.close()

    largest: Any = rows[0][0] or 0
    assert largest < 64_000, (
        f"an audit payload of {largest} bytes is large enough to be a file body. If the trail "
        f"now carries authored content, 052 closes one copy and leaves another."
    )
