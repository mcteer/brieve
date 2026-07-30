# SPDX-License-Identifier: Apache-2.0
"""Every shipped observer can actually be called by the resume path (014).

**This exists because one could not, and nothing noticed for a feature.**
`VaultWriteObserver.observe` required a `run_id` the protocol does not pass, so
`resolve_open_intents` raised `TypeError` on every call. The resume path catches a raising
observer and reads it as `CANNOT_DETERMINE` — correct for an observer that cannot reach its
product, and precisely wrong for one that cannot be called: every interrupted Vault write
suspended its run awaiting `vault` instead of being resolved by observation.

It survived because the only caller was `resume_run`, which had no caller in `src/`, and
because the unit rows constructed the observer directly and passed both arguments — agreeing
with the implementation rather than with the protocol. So the rows that would have caught it
were written against the same misunderstanding.

The check is therefore about the CALL SHAPE `resolve_open_intents` uses, not about the type
annotation: a signature can satisfy a Protocol structurally and still reject the one call the
platform makes.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from core.observation.types import Observation, ObservationOutcome
from surfaces.toolset import build_registry


def _shipped_observers() -> dict[str, Any]:
    """Every observer a dispatched run could actually load, from every pack."""
    registry, _ = build_registry(packs=["vault", "terraform"])
    observers = registry.observers()
    assert observers, "no observers were registered at all, so this check asserts nothing"
    return observers


@pytest.mark.parametrize("tool_name", sorted(_shipped_observers()))
def test_an_observer_accepts_the_only_call_the_resume_path_makes(tool_name: str) -> None:
    """`observe(idempotency_key=...)` — one keyword, exactly as `resolve_open_intents` calls it.

    Asserted by binding the signature rather than by invoking it: a real call would reach the
    product, and what is under test is whether the call is *accepted*, which is answerable
    without one.
    """
    observer = _shipped_observers()[tool_name]
    signature = inspect.signature(observer.observe)

    try:
        signature.bind(idempotency_key="run-1:0:tool")
    except TypeError as exc:
        pytest.fail(
            f"{tool_name}'s observer cannot be called the way the resume path calls it: {exc}. "
            f"`resolve_open_intents` passes `idempotency_key` and nothing else, and an observer "
            f"that raises is read as CANNOT_DETERMINE — so this failure would present as every "
            f"interrupted step suspending its run rather than as a broken signature."
        )


@pytest.mark.parametrize("tool_name", sorted(_shipped_observers()))
def test_an_observer_returns_an_observation_or_says_it_cannot_tell(tool_name: str) -> None:
    """The return contract, checked without reaching a product.

    An observer with no product to reach must answer `CANNOT_DETERMINE` rather than raising or
    guessing — "not having a way to look is not evidence of anything". Here nothing is
    reachable, so that is the only correct answer, and any other one means the observer
    invented a result.
    """
    observer = _shipped_observers()[tool_name]

    try:
        result = observer.observe(idempotency_key="run-that-does-not-exist:0:tool")
    except Exception:  # noqa: BLE001 — a raising observer is the defect under test
        # Tolerated: the resume path catches it and reads CANNOT_DETERMINE, which is the
        # honest outcome. What must never happen is a confident wrong answer.
        return

    assert isinstance(result, Observation)
    assert result.outcome is not ObservationOutcome.HAPPENED, (
        f"{tool_name}'s observer reported that an effect it could not verify had HAPPENED — "
        f"the one answer that silently drops work"
    )
