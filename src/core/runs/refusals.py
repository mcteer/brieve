# SPDX-License-Identifier: Apache-2.0
"""What an operation says, and what the trail records — two different questions.

FR-020's split, in one place so it cannot drift apart across six operations. The caller
sees *no such thing* whether the record is absent or belongs to another tenant; the trail
records which it was.

**Why the collapse is right for the caller**: an operation that distinguished "does not
exist" from "not yours" would let anyone enumerate another tenant's identifiers by
probing — the response itself becomes an oracle. **Why the distinction is right for the
trail**: an investigator looking at a run of `outside_tenant` entries is looking at
probing, and a trail that had collapsed them would show only a user who mistypes a lot.
"""

from __future__ import annotations

from typing import Final

#: Every refusal an operation in this package may report, and what each means.
#:
#: A frozen mapping rather than bare strings, on the 010 pattern: a reason code invented at
#: a call site is one nothing can assert on, and six operations refusing in five slightly
#: different vocabularies is how a conformance row stops being writable.
OPERATION_REASONS: Final[dict[str, str]] = {
    "no_such_record": "no record with that identifier exists",
    "outside_tenant": "the record exists in another tenant",
    "not_permitted": "the record is visible to this caller, and this action is not theirs",
    # 012's additions. Both are *pre-acceptance* — the platform never considered the
    # message, so neither produces a turn, and both are recorded as TURN_REFUSED rather
    # than TURN_RECORDED.
    "rate_limited": "this subject has taken too many acts in the rate window",
    "message_too_large": "the message exceeds the stated size bound and is refused whole",
    # Not a refusal of the caller at all: the platform cannot do this for anyone.
    # Distinct from `not_permitted` because conflating them tells someone their access is
    # fine when it is not, and tells another that it is not when it is.
    "nothing_to_dispatch": "no agent was selected, and none is available to dispatch",
}

# 013's vocabulary is deliberately NOT here. Every matrix, pack, and tier refusal is raised
# as `ResolutionRefused`, which validates against `RESOLUTION_REASONS` in
# `core.authority.errors` — a different frozen mapping, and the one the code actually
# checks. The task list said to extend this one; the code says otherwise, and the code is
# what refuses at construction. Load-time refusals (digest, coverage, governance hook)
# carry `ManifestError` and belong to neither mapping: they refuse a pack before any
# operation or resolution has begun.

#: The reasons a caller must not be able to tell apart.
#:
#: Both answer "not found" on the wire. Keeping the set explicit means the collapse is a
#: decision a reader can find, rather than an accident of two branches returning the same
#: status.
INDISTINGUISHABLE_TO_CALLER: Final[frozenset[str]] = frozenset({"no_such_record", "outside_tenant"})


class OperationRefused(Exception):
    """An operation declined. Carries what the trail records, not what the caller sees.

    Refuses an unknown reason code at construction — the same guard
    `ResolutionRefused` carries, for the same reason: accepting one would reintroduce
    call-site invention one operation at a time.
    """

    def __init__(self, message: str, *, reason_code: str) -> None:
        if reason_code not in OPERATION_REASONS:
            raise ValueError(
                f"unknown operation reason code {reason_code!r}; "
                f"add it to OPERATION_REASONS with what it means"
            )
        super().__init__(message)
        self.reason_code = reason_code

    @property
    def is_visible_to_caller(self) -> bool:
        """Whether the caller learns this refusal's real reason.

        ``False`` means the caller is told "not found" regardless — the tenant boundary
        answering, rather than the operation.
        """
        return self.reason_code not in INDISTINGUISHABLE_TO_CALLER


__all__ = [
    "INDISTINGUISHABLE_TO_CALLER",
    "OPERATION_REASONS",
    "OperationRefused",
]
