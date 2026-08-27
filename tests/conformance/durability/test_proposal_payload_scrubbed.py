# SPDX-License-Identifier: Apache-2.0
"""GATE — the call site, from both directions (052, T018-T028, rows A4, A5, A9, A17-A20).

US1 says the scrub happens. US3 says it does **not** happen in the two places that would break
the platform. They are the same call site seen from two sides, which is why they are one file:
a change that satisfies one and breaks the other should fail here rather than in a lane
somebody runs later.

**The rows that read columns rather than payloads are the ones to keep.** Every other assertion
in this feature inspects `payload`, so none of them would notice a re-save that blanked
`correlation_id` — the join prompt → hook → tool → product → audit is walked along, in the
feature whose second half is keeping a finished run attestable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob, RunOutcome
from core.run import RunState
from surfaces.dispatch.entrypoint import ScrubFailed, _scrub_the_proposal
from tests.fixtures.authoring_payloads import authored_payload, empty_payload
from tests.harness.secrets import AUTHORING_SUBJECT_SECRET_MARKER

ROOT = Path(__file__).resolve().parents[3]

BLOB = "propose-052-callsite"

#: Every column `save()` overwrites. The guarded ones and the unguarded ones together, because
#: a row that checked only the unguarded ones would stop noticing if a guard were removed.
COLUMNS = ("correlation_id", "grant_id", "step_index", "written_by", "resume_count")


def _blob(payload: dict[str, Any] | None = None) -> CheckpointBlob:
    """A terminal checkpoint as `_publish_the_proposal` leaves one."""
    return CheckpointBlob(
        blob_id=BLOB,
        payload=payload if payload is not None else authored_payload(),
        correlation_id="corr-052-abcdef",
        grant_id="grant-052-abcdef",
        step_index=7,
        written_by="entrypoint",
        outcome=RunOutcome(state=RunState.COMPLETED.value, stop_reason=None),
        resume_count=2,
    )


@pytest.fixture
def provider() -> InMemoryDurabilityProvider:
    store = InMemoryDurabilityProvider()
    store.save(_blob())
    return store


def _scrub(store: InMemoryDurabilityProvider) -> None:
    _scrub_the_proposal(store, blob_id=BLOB, correlation_id="corr-052-abcdef")


# ------------------------------------------------------------------ US1: it happens


def test_the_stored_payload_holds_no_authored_body_afterwards(provider: Any) -> None:
    """Row A9, and the point of the feature. Read the store back, not the return value."""
    before = provider.load(BLOB)
    assert AUTHORING_SUBJECT_SECRET_MARKER in str(before.payload), (
        "the fixture no longer carries the marker, so this row asserts an absence of nothing"
    )

    _scrub(provider)

    assert AUTHORING_SUBJECT_SECRET_MARKER not in str(provider.load(BLOB).payload)


def test_the_manifest_survives_in_the_store(provider: Any) -> None:
    """US2 through the real path: paths and digests still there, bodies not."""
    _scrub(provider)
    proposal = provider.load(BLOB).payload["authoring_proposal"]
    assert [f["path"] for f in proposal["files"]] == ["src/config/vaultConfig.js", "main.tf"]
    assert any("` — `" in line for line in proposal["provenance"])


# ------------------------------------------------------------------ A17/A19: the columns


@pytest.mark.parametrize("column", COLUMNS)
def test_every_column_survives_the_re_save(provider: Any, column: str) -> None:
    """ROW A17 — the row no other assertion in this feature could stand in for.

    `save()` overwrites the whole row. `run_state`, `stop_reason` and `resume_count` carry
    guards, each added after somebody lost that column; `correlation_id`, `grant_id`,
    `step_index` and `written_by` do not. A bare
    `CheckpointBlob(blob_id=…, payload=scrubbed)` blanks the correlation ID and every other row
    here — all of which read `payload` — would still pass.
    """
    before = getattr(provider.load(BLOB), column)
    _scrub(provider)
    assert getattr(provider.load(BLOB), column) == before, column


def test_the_run_stays_terminal(provider: Any) -> None:
    """The guarded columns, asserted anyway. A guard nobody checks is a guard nobody maintains."""
    _scrub(provider)
    outcome = provider.load(BLOB).outcome
    assert outcome is not None
    assert outcome.state == RunState.COMPLETED.value


def test_the_pull_request_url_survives(provider: Any) -> None:
    """ROW A19 — the field the recorded defect actually lost.

    Re-saving from the pre-publish `checkpoint` in scope "restored the analyzer snapshot, wiped
    `pr_url`, and left Nomad 'complete' looking like 'Ended without a pull request.'" This is
    what proves the terminal blob was re-read instead.
    """
    _scrub(provider)
    result = provider.load(BLOB).payload["__run_result__"]
    assert result["pr_url"] == "https://github.com/acme/infra/pull/7"


def test_the_scrubbed_marker_reaches_the_store(provider: Any) -> None:
    """Row A20. Without it, the publish-time refusal has nothing to key on."""
    _scrub(provider)
    assert provider.load(BLOB).payload["authoring_proposal"]["scrubbed"] is True


# ------------------------------------------------------------------ US3: it does not happen


def test_a_run_that_authored_nothing_writes_nothing(provider: Any) -> None:
    """Row A7 through the call site: no proposal, no save, no error."""
    provider.save(_blob(payload=empty_payload()))
    _scrub(provider)
    assert provider.load(BLOB).payload == empty_payload()


def test_scrubbing_twice_is_safe(provider: Any) -> None:
    """Row A8. Terminal state can be reached more than once."""
    _scrub(provider)
    first = provider.load(BLOB).payload
    _scrub(provider)
    assert provider.load(BLOB).payload == first


def test_a_missing_checkpoint_is_not_an_error() -> None:
    """A run whose terminal blob cannot be read never wrote a payload for this to clear."""
    _scrub_the_proposal(InMemoryDurabilityProvider(), blob_id=BLOB, correlation_id="c")


# ------------------------------------------------------------------ FR-005: fail closed


def test_a_save_that_does_not_take_effect_raises(provider: Any) -> None:
    """ROW A9's second half, and the failure nothing can detect afterwards.

    A scrub that returned quietly while leaving the content in place would record a retention
    guarantee the store does not hold, and every later reader sees a completed run with no
    reason to look again. Verified by reading the store back rather than by trusting `save`.
    """

    class SilentlyDiscards(InMemoryDurabilityProvider):
        """A store whose `save` succeeds and changes nothing — the shape FR-005 is about."""

        def save(self, blob: CheckpointBlob) -> None:
            return

    store = SilentlyDiscards()
    InMemoryDurabilityProvider.save(store, _blob())  # seed past the discarding override

    with pytest.raises(ScrubFailed) as caught:
        _scrub_the_proposal(store, blob_id=BLOB, correlation_id="c")
    assert BLOB in str(caught.value)


def test_the_fail_closed_row_can_pass(provider: Any) -> None:
    """The control. A guard that fired on a working store would be indistinguishable."""
    _scrub(provider)


# ------------------------------------------------------------------ A4/A5: the gating


def test_the_analyzer_branch_does_not_scrub() -> None:
    """ROW A4 — the way this feature ships broken.

    The intents scrub one line above is gated `authoring_role(...) is not None`, which is **true
    in the analysing task too**. That is safe for intents, whose SQL clears closed brackets only,
    and would be a defect here: the analyzer's checkpoint IS the handoff the proposer reads, so
    scrubbing it there makes every interrupted publish resume with nothing to publish.

    Read from the source, because the failure is a one-word edit to a condition and no runtime
    fixture distinguishes the two branches as cheaply.
    """
    source = (ROOT / "src" / "surfaces" / "dispatch" / "entrypoint.py").read_text(encoding="utf-8")
    call = source.index("_scrub_the_proposal(durability")
    guard = source.rindex("if authoring_role(", 0, call)
    condition = source[guard : source.index(":", guard)]
    assert "PROPOSER" in condition, (
        "the payload scrub is not gated to the proposer branch. Copying the intents scrub's "
        f"`is not None` gate would scrub the analyzer handoff. Found: {condition.strip()!r}"
    )


def test_the_intents_scrub_keeps_its_wider_gate() -> None:
    """The other half: A4 must not be satisfied by narrowing the scrub beside it.

    041 gates the intents scrub on both branches deliberately, and a change that narrowed it to
    match would silently stop scrubbing the analyser's closed brackets.
    """
    source = (ROOT / "src" / "surfaces" / "dispatch" / "entrypoint.py").read_text(encoding="utf-8")
    call = source.index("scrub_authoring_requests(durability")
    guard = source.rindex("if authoring_role(", 0, call)
    assert "is not None" in source[guard : source.index(":", guard)]


def test_a_failed_publish_leaves_the_payload_intact() -> None:
    """ROW A5. `_publish_the_proposal` returning non-zero returns before the scrub is reached,
    so the resumption still has what it needs.

    Asserted at the call site's own control flow: the scrub is unreachable when publish fails.
    """
    source = (ROOT / "src" / "surfaces" / "dispatch" / "entrypoint.py").read_text(encoding="utf-8")
    published = source.index("published = _publish_the_proposal(")
    scrub = source.index("_scrub_the_proposal(durability")
    between = source[published:scrub]
    assert "if published != 0:" in between and "return published" in between, (
        "a failed publish no longer returns before the payload scrub, so a retry would find "
        "its proposal cleared"
    )
