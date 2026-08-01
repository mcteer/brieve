# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — the merge lane needs no vendor, and the double it uses is checked (020).

**A double nobody checks is a double that drifts**, and this feature exists to end exactly
that shape: something correct, tested, and standing in for a thing that was never exercised.
So the lane's stand-in is asserted faithful rather than trusted.

The fidelity row costs a provider call, so it cannot be in the merge lane — which is the
tension FR-011 and FR-011a hold together. FR-011 says a gate that cannot run without a vendor
is a gate that stops running; FR-011a says a stand-in nobody checks is worthless. The
resolution is that fidelity is checked **periodically, behind a named runner**, and the limit
is recorded rather than closed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from adapters.model_chooser import build_chooser, to_model_string
from core.choice import ChoiceRequest, ChooserUnavailable
from core.evals.scoring import EVAL_PROVIDER_KEY, LIVE_MODEL
from tests.harness.scripted_chooser import FIXTURE_MODEL, recording

ROOT = Path(__file__).resolve().parents[3]

#: One fixture, put to both. The task and the ceiling a fidelity comparison uses.
FIXTURE_TASK = "Read the current value stored at conformance/probe."
FIXTURE_PERMITTED = ("echo", "plan")


def test_the_merge_lane_needs_no_provider() -> None:
    """FR-011, SC-006 — every model the blocking lane reaches replays a recording.

    Two things are checked, and the second is the one that could rot. The first: a fixture
    chooser answers without a credential present. The second: the *matrix the enclave ships*
    qualifies only `fixture/...` cells, so no dispatched row can reach a vendor even by
    accident — a live cell added for a demonstration and left behind would make the merge
    gate depend on a vendor without anyone changing a test.
    """
    chooser = build_chooser(FIXTURE_MODEL, recording=recording("plan", "echo"))
    request = ChoiceRequest(task=FIXTURE_TASK, permitted=FIXTURE_PERMITTED, step_index=0, attempt=0)
    assert chooser.choose(request) == "plan"

    variables = (ROOT / "infra/environments/dev/variables.tf").read_text()
    matrix = variables.split('variable "model_matrix_cells"', 1)
    assert len(matrix) == 2, "the dev environment no longer declares model_matrix_cells"
    assert 'qualified_by = "live"' not in matrix[1], (
        "a LIVE matrix cell ships in the dev enclave, so a dispatched conformance row could "
        "reach a vendor — the merge lane would then fail for reasons unrelated to the code, "
        "which is how a gate stops being run"
    )


def test_a_fixture_cell_without_a_recording_is_loud() -> None:
    """A misconfiguration must not present as a model that chose nothing.

    Answering `""` here would end every such run terminally while looking exactly like a
    model declining to act — a green-looking failure, which is the shape FR-011a exists to
    prevent one level up.
    """
    with pytest.raises(ChooserUnavailable) as excinfo:
        build_chooser(FIXTURE_MODEL, recording="")
    assert excinfo.value.reason_code == "recording_missing"


def test_the_identifier_the_matrix_pins_is_the_one_called() -> None:
    """The join the matrix exists to keep tight.

    `provider/model@version` is enforced at parse precisely so what is pinned is what is
    called. A mapping that dropped the version would send every request to whatever the
    provider's default happened to be that week — auto-tracking under another name, which is
    what FR-011 of 013 forbade and what this identifier format was chosen to make
    inexpressible.
    """
    assert to_model_string("anthropic/claude-opus@5") == "anthropic:claude-opus-5"
    assert to_model_string(LIVE_MODEL) == "anthropic:claude-opus-5"


@pytest.mark.live_model
def test_the_double_is_faithful() -> None:
    """FR-011a — the double and a real provider agree in SHAPE on one fixture.

    **Not on which tool.** Two models may reasonably differ, and a row demanding they match
    would be asserting a model's judgement rather than the platform's contract. What must
    agree is that both return a well-formed choice from the permitted set — because that is
    the whole of what the rest of the platform relies on the chooser to do.

    Behind `live_model` with a named runner (Dan McTeer), like `make evals-live`: it costs a
    provider call, so it cannot be in the merge lane. That makes the guarantee **periodic**
    rather than continuous, and the double could drift between checks. Recorded in the
    conformance contract rather than papered over — the alternative is a merge lane that
    needs a vendor.

    Raises rather than skips when the credential is absent, on 013's SC-005a reasoning: an
    unrunnable gate that skips is a gate that reports green having tested nothing.
    """
    if not os.environ.get(EVAL_PROVIDER_KEY, "").strip():
        pytest.fail(
            f"the fidelity row has no provider credential ({EVAL_PROVIDER_KEY} is unset). "
            f"It raises rather than skipping: a double whose fidelity check silently did not "
            f"run is a double nobody checks, which is what FR-011a exists to prevent"
        )

    request = ChoiceRequest(task=FIXTURE_TASK, permitted=FIXTURE_PERMITTED, step_index=0, attempt=0)
    double = build_chooser(FIXTURE_MODEL, recording=recording("plan"))
    live = build_chooser(LIVE_MODEL)

    answers = {"double": double.choose(request), "live": live.choose(request)}
    for which, answer in answers.items():
        assert answer in FIXTURE_PERMITTED, (
            f"the {which} chooser answered {answer!r}, which is not a well-formed choice from "
            f"the permitted set {FIXTURE_PERMITTED} — the double and the provider no longer "
            f"agree in shape, so every lane using the double is asserting governance around "
            f"a stand-in for a decision it does not resemble"
        )
