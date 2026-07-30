# SPDX-License-Identifier: Apache-2.0
"""A resume is declared by the dispatcher, never inferred by the entrypoint (014 T011, D1).

**Why inference was rejected, since a reader's first instinct is that it would be simpler.**
Two candidate signals exist, and each turns a coincidence into a resume:

- ``step_index > 0`` misses a run interrupted at step zero, which then starts over. Silent,
  and indistinguishable from a run that had not begun.
- "a checkpoint exists for this ``run_id``" turns an **id collision** into a silent resume.
  The jobspec's own ``meta_required`` comment already documents this failure for ``run_id``:
  a dispatch that reuses a resumed run's identifiers "looks like a successful resume and
  re-executes everything the run had already done". Inference makes that reachable from a
  collision rather than from a mistake.

The dispatcher *knows* — the sweeper is the only component that dispatches a revival — so
the knowledge travels as data instead of being reconstructed downstream from evidence that
is consistent with two different histories.

These rows read the dispatch PAYLOAD rather than standing up a scheduler: what is under test
is the metadata contract between the dispatcher and the jobspec, and the enclave rows drive
the whole path.
"""

from __future__ import annotations

from typing import Any

from surfaces.dispatch.nomad import NomadDispatcher


class _CapturingDispatcher(NomadDispatcher):
    """Records the payload instead of submitting it.

    Subclassed at `_request` — the seam just below the metadata construction — so everything
    this row asserts is built by the real `dispatch()`. A hand-rolled fake would assert the
    fake's idea of the payload.
    """

    def __init__(self) -> None:
        super().__init__()
        self.payloads: list[dict[str, Any]] = []

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if payload is not None:
            self.payloads.append(payload)
        return {"DispatchedJobID": "agent-run/dispatch-1"}

    @property
    def last_meta(self) -> dict[str, str]:
        return dict(self.payloads[-1]["Meta"])


def _dispatch(dispatcher: NomadDispatcher, **kw: Any) -> None:
    dispatcher.dispatch(
        correlation_id="corr-1",
        subject_user_id="user-1",
        tenant_id="tenant-1",
        agent_definition_id="definition-1",
        requested_tools=frozenset({"echo"}),
        **kw,
    )


def test_a_fresh_dispatch_does_not_claim_to_be_a_resume() -> None:
    dispatcher = _CapturingDispatcher()
    _dispatch(dispatcher)

    # Present and empty, not absent. Nomad rejects any metadata key declared in neither
    # meta list, so the key must always travel; its VALUE is the discriminator.
    assert dispatcher.last_meta["resume"] == ""


def test_a_resume_dispatch_declares_itself() -> None:
    dispatcher = _CapturingDispatcher()
    _dispatch(dispatcher, run_id="run-7", step_index=3, resume=True)

    assert dispatcher.last_meta["resume"] == "1"


def test_a_dispatch_carrying_resume_identifiers_without_the_flag_is_not_a_resume() -> None:
    """The id-collision edge case, and the whole point of D1.

    A used ``run_id`` and a non-zero ``step_index`` are exactly what a resume carries. This
    dispatch carries both and is still not a resume, because the flag — not the identifiers
    — is what the entrypoint reads. Inference from either signal would make this dispatch
    skip work it never did.
    """
    dispatcher = _CapturingDispatcher()
    _dispatch(dispatcher, run_id="run-7", step_index=3)

    meta = dispatcher.last_meta
    assert meta["run_id"] == "run-7"
    assert meta["step_index"] == "3"
    assert meta["resume"] == "", "identifiers must not imply a resume"


def test_the_flag_is_the_only_metadata_the_resume_changes() -> None:
    """A resume dispatch differs from a fresh one in exactly one key.

    Asserted because the alternative D1 rejected was a second parameterized job for
    resumes: two jobspecs that must stay identical except one flag is drift waiting to
    happen. This row is that rejection kept honest — if the resume path ever starts needing
    its own metadata shape, this fails and the decision gets revisited deliberately.
    """
    fresh = _CapturingDispatcher()
    _dispatch(fresh, run_id="run-7", step_index=3)

    resumed = _CapturingDispatcher()
    _dispatch(resumed, run_id="run-7", step_index=3, resume=True)

    differing = {
        key
        for key in fresh.last_meta.keys() | resumed.last_meta.keys()
        if fresh.last_meta.get(key) != resumed.last_meta.get(key)
    }
    assert differing == {"resume"}
