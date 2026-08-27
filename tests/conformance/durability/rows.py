# SPDX-License-Identifier: Apache-2.0
"""Shared assertions for the seven durability rows.

Extracted so each row's **break fixture** can exercise the same assertion against a
deliberately weakened arrangement. A gate nobody has watched fail is a gate nobody
knows works (FR-014).
"""

from __future__ import annotations

import re

from core.durability.types import CheckpointBlob, DurabilityProvider
from core.observation.types import ObservationOutcome
from core.run import RunState

#: Substrings that only ever appear in credential MATERIAL. Matched raw, because none of
#: them is an English word somebody could write about.
CREDENTIAL_MARKERS = ("hvs.", "hvb.", "-----begin", "run_salt")

#: Field names whose VALUE would be credential material. Matched as a key-with-value pair,
#: never as a bare word.
#:
#: THE BARE WORD WAS THE BUG (2026-08-27). This swept `str(row).lower()` for `"secret"`, and a
#: Judge model's own prose — *"the slice is on-topic and secret-free"* — matched it. A gate
#: proving the store holds no authority went red because a model said the word while reporting
#: the absence of the thing. It is the same shape this repository has caught four times before:
#: a check matching prose instead of structure.
#:
#: A credential in a checkpoint is a VALUE UNDER A KEY. `"vault_token": "hvs.abc"` is the
#: leak; `secret-free` in a sentence is not, and cannot be made into one.
CREDENTIAL_FIELDS = ("credential", "token", "secret", "password", "private_key", "api_key")

#: `"token": "value"` and `'token': 'value'` — JSON and Python-repr, because a row renders
#: through `str()` and a payload through `model_dump()`. A non-empty value is required: an
#: empty or null field carries nothing.
#: The key may be quoted (`"token":`) or bare (`client_secret =`). The bare form was missed on
#: the first attempt and `test_credential_material_matcher` caught it — a config-file or
#: environment assignment is as much a leak as a JSON field, and requiring quotes would have
#: shipped a matcher blind to `.env`-shaped material.
_FIELD_WITH_VALUE = re.compile(
    r"""(?ix)
    ["']?                                  # optional opening quote of the key
    \b[a-z0-9_.\-]*                        # any prefix: vault_token, app_secret
    (?:"""
    + "|".join(CREDENTIAL_FIELDS)
    + r""")
    [a-z0-9_.\-]*\b                        # any suffix: token_id, secret_ref
    ["']?                                  # optional closing quote
    \s*[:=]\s*                             # : in a mapping, = in an assignment
    ["'][^"']+["']                         # a NON-EMPTY string value
    """
)


def credential_material_in(rendered: str) -> str | None:
    """The first sign of credential material in ``rendered``, or None.

    One definition, used by the blob-level sweep and the live-table one, so the two cannot
    drift into disagreeing about what a secret looks like — which they already had, silently:
    two tuples, one carrying `hvs.` and `private_key` and the other not.
    """
    lowered = rendered.lower()
    for marker in CREDENTIAL_MARKERS:
        if marker in lowered:
            return marker
    found = _FIELD_WITH_VALUE.search(rendered)
    return found.group(0) if found else None


#: Kept for callers that still want the raw field names.
FORBIDDEN_IN_CHECKPOINTS = CREDENTIAL_FIELDS


def assert_resumes_from_checkpoint(blob: CheckpointBlob | None, *, expected_step: int) -> None:
    assert blob is not None, "no checkpoint: nothing to resume from"
    assert blob.step_index == expected_step, "resumed from the wrong point"


def assert_executed_exactly_once(counts: dict[str, int], step: str) -> None:
    """Across the whole run, not per segment — a per-segment count passes a replayer."""
    assert counts.get(step, 0) == 1, f"{step} executed {counts.get(step, 0)} times, expected 1"


def assert_no_credential_in_checkpoint(blob: CheckpointBlob) -> None:
    found = credential_material_in(str(blob.model_dump()))
    assert found is None, f"checkpoint contains credential material: {found!r}"


def assert_fresh_authority(before_id: str, after_id: str | None) -> None:
    assert after_id is not None, "resume manufactured no authority"
    assert after_id != before_id, "resume reused the pre-disruption credential"


def assert_superseded_is_rejected(provider: DurabilityProvider, run_id: str, stale: str) -> None:
    assert not provider.check_lease(run_id, stale), "a superseded holder still holds the lease"


def assert_stopped(state: RunState, reason: str | None, *, expected_prefix: str) -> None:
    """The grant-expiry row, as ADR-0049 redefines it.

    It asserted PARKED — "stopped for a human to resolve" — and now asserts STOPPED,
    because there is no human to resolve it. The constitution's Quality Gates named this
    row "grant-expiry parking"; the amendment in this change renames it to grant-expiry
    stop, so the governing document and this assertion say the same thing.

    STOPPED is terminal, which is the substantive difference: nothing resumes it, and a
    row that still accepted a resumable state would let a run continue past a bound.
    """
    assert state is RunState.STOPPED, f"expected STOPPED, got {state}"
    assert state.is_terminal(), "grant expiry must be terminal — nothing resumes a bound"
    assert reason is not None and reason.startswith(expected_prefix), (
        f"stop reason {reason!r} does not start with {expected_prefix!r}"
    )


def assert_suspended(state: RunState, awaiting: str | None, *, expected: str) -> None:
    """The other half of what PARKED conflated: waiting on a machine condition.

    Resumable by construction — asserted, because a suspension that reported terminal
    would be a run the sweeper can never pick up, and it would look like a hang.
    """
    assert state is RunState.SUSPENDED, f"expected SUSPENDED, got {state}"
    assert not state.is_terminal(), "a suspended run must stay resumable"
    assert awaiting == expected, f"suspended awaiting {awaiting!r}, expected {expected!r}"


def assert_observation_decides(outcome: ObservationOutcome, *, repeated: bool) -> None:
    """The decision must match what was observed, in both directions."""
    if outcome is ObservationOutcome.HAPPENED:
        assert not repeated, "repeated a step observed to have already taken effect"
    elif outcome is ObservationOutcome.DID_NOT_HAPPEN:
        assert repeated, "skipped a step observed not to have taken effect"
    else:  # pragma: no cover - cannot-determine must park before reaching here
        raise AssertionError("cannot_determine must park, not resolve to a decision")


def assert_same_step_same_key(first: str, second: str) -> None:
    assert first == second, "a retry of the same step produced a different identity"


def assert_evidence_spans_disruption(blob: CheckpointBlob, correlation_id: str) -> None:
    assert blob.correlation_id == correlation_id, "the join key did not survive the boundary"
