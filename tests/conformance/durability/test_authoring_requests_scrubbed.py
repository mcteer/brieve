# SPDX-License-Identifier: Apache-2.0
"""A22 — a finished authoring run leaves no subject content in the control plane (041, FR-033).

**Both providers, and the Postgres leg is the one that counts.** The in-memory provider stores
a record object and clears a field for free, so a scrub proven only against it would pass
whether or not the SQL was ever written — 040's M7 shape, one column over. The Postgres row is
enclave-marked because it needs a real database; it fails rather than skips when absent.

**Closed brackets only**, which is 040's own bound: resume reads arguments for pending steps,
so clearing an OPEN bracket would make that revival re-invoke with an empty request. A row
asserts the open case survives, because a scrub that took too much would be a durability defect
wearing a security fix's clothes.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.authoring.retention import scrub_authoring_requests
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import IntentRecord, ResultRecord

RUN = "run-041-scrub"
SECRET_BODY = 'resource "aws_iam_user" "x" { name = "customer-private-content" }\n'


def _intent(
    key: str, *, tool: str = "author_file", arguments: dict[str, object] | None = None
) -> IntentRecord:
    return IntentRecord(
        run_id=RUN,
        idempotency_key=key,
        step_index=1,
        tool_name=tool,
        arguments=arguments
        if arguments is not None
        else {"path": "main.tf", "content": SECRET_BODY},
        recorded_at=datetime.now(UTC),
    )


def _result(key: str) -> ResultRecord:
    return ResultRecord(
        run_id=RUN, idempotency_key=key, step_index=1, recorded_at=datetime.now(UTC)
    )


def test_row_a22_a_closed_authoring_act_is_scrubbed() -> None:
    """The content a customer owns does not outlive the run that produced it."""
    provider = InMemoryDurabilityProvider()
    provider.record_intent(_intent("k1"))
    provider.record_result(_result("k1"))

    scrubbed = scrub_authoring_requests(provider, run_id=RUN)

    assert scrubbed == 1
    remaining = provider.closed_intents(RUN)
    assert remaining and remaining[0].arguments is None
    assert SECRET_BODY not in repr(remaining)


def test_row_a22_an_open_bracket_keeps_its_arguments() -> None:
    """040's bound, asserted: an open bracket revives by RE-INVOKING and needs the request."""
    provider = InMemoryDurabilityProvider()
    provider.record_intent(_intent("open-1"))

    scrubbed = scrub_authoring_requests(provider, run_id=RUN)

    assert scrubbed == 0
    pending = provider.open_intents(RUN)
    assert pending and pending[0].arguments is not None, (
        "clearing an open bracket would make the revival re-invoke with nothing, which is a "
        "durability defect wearing a security fix's clothes"
    )


def test_row_a22_another_runs_records_are_untouched() -> None:
    """The scrub is per run. A cleanup that reached across runs would be a different bug."""
    provider = InMemoryDurabilityProvider()
    provider.record_intent(_intent("k1"))
    provider.record_result(_result("k1"))
    other = IntentRecord(
        run_id="some-other-run",
        idempotency_key="k1",
        step_index=1,
        tool_name="author_file",
        arguments={"path": "a.tf", "content": "other run's content"},
        recorded_at=datetime.now(UTC),
    )
    provider.record_intent(other)
    provider.record_result(
        ResultRecord(
            run_id="some-other-run",
            idempotency_key="k1",
            step_index=1,
            recorded_at=datetime.now(UTC),
        )
    )

    scrub_authoring_requests(provider, run_id=RUN)

    survived = provider.closed_intents("some-other-run")
    assert survived and survived[0].arguments is not None


def test_row_a22_scrubbing_twice_is_safe() -> None:
    """Terminal state may be reached more than once."""
    provider = InMemoryDurabilityProvider()
    provider.record_intent(_intent("k1"))
    provider.record_result(_result("k1"))

    assert scrub_authoring_requests(provider, run_id=RUN) == 1
    assert scrub_authoring_requests(provider, run_id=RUN) == 0


def test_row_a22_a_run_that_authored_nothing_scrubs_cleanly() -> None:
    """A successful run and an empty one must not take different cleanup paths."""
    provider = InMemoryDurabilityProvider()
    assert scrub_authoring_requests(provider, run_id=RUN) == 0


def test_a_provider_without_the_method_does_not_fail_a_finished_run() -> None:
    """An older provider is a deployment fact, not a reason to fail work already done."""

    class Older:
        pass

    assert scrub_authoring_requests(Older(), run_id=RUN) == 0


@pytest.mark.enclave
def test_row_a22_the_postgres_leg(postgres_durability) -> None:  # type: ignore[no-untyped-def]
    """The leg that counts. In-memory clears a field for free; this proves the SQL exists."""
    provider = postgres_durability
    provider.record_intent(_intent("pg-closed"))
    provider.record_result(_result("pg-closed"))
    provider.record_intent(_intent("pg-open"))

    scrubbed = scrub_authoring_requests(provider, run_id=RUN)

    assert scrubbed == 1
    closed = [i for i in provider.closed_intents(RUN) if i.idempotency_key == "pg-closed"]
    assert closed and closed[0].arguments is None
    still_open = [i for i in provider.open_intents(RUN) if i.idempotency_key == "pg-open"]
    assert still_open and still_open[0].arguments is not None
