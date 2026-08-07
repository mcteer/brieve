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
import re
from pathlib import Path

import pytest

from adapters.model_chooser import build_chooser, to_model_string
from core.choice import CHOICE_ROLE, Answer, ChoiceRequest, ChooserUnavailable
from core.evals.scoring import EVAL_PROVIDER_KEY, LIVE_MODEL
from tests.harness.scripted_chooser import FIXTURE_MODEL, recording

ROOT = Path(__file__).resolve().parents[3]

#: One fixture, put to both — and the task and the permitted set must COHERE.
#:
#: The first version paired that task with ``("echo", "plan")``, and the live model answered
#: NONE: neither tool reads a secret, so declining was the correct choice and the row failed on
#: a disagreement that was not a fidelity problem at all. FR-011a asserts both choosers return
#: a *well-formed choice from the permitted set*, which presumes the set contains something the
#: task could plausibly want. An incoherent fixture tests whether a model will invent a use for
#: the wrong tool, which is the opposite of what this platform wants a model to do.
FIXTURE_TASK = "Read the current value stored at conformance/probe."
FIXTURE_PERMITTED = ("vault_read", "vault_write")


#: Roles reachable only from an ANSWERING SURFACE, never from a dispatched run — so a live cell
#: in one of them cannot make a dispatched conformance row reach a vendor.
#:
#: **Narrowed a second time, on the same reasoning that narrowed it first** (2026-08-07, 043).
#: The check began as "no live cell at all", and 2026-08-02 narrowed it to permit `ask` once the
#: first live cell was earned, with the principle written into the docstring below: a dispatched
#: run resolves `CHOICE_ROLE` and nothing else. `judge` is the role 043's relevance gate
#: resolves, and it resolves it on the ask path — structurally the same position as `ask`, which
#: this row already permits. The implementation was broader than the stated principle, and this
#: is the principle applied rather than the guard relaxed.
#:
#: `plan`, `write` and `summarize` still fail. `write` most of all: a model permitted to make
#: changes is the one the enclave must never reach by accident.
SURFACE_ONLY_ROLES = frozenset({"ask", "judge"})


def test_the_merge_lane_needs_no_provider() -> None:
    """FR-011, SC-006 — every model the blocking lane reaches replays a recording.

    Two things are checked, and the second is the one that could rot. The first: a fixture
    chooser answers without a credential present. The second: the matrix the enclave ships
    qualifies no live cell **in a role a dispatched run resolves**, so no dispatched row can
    reach a vendor even by accident — a live cell added for a demonstration and left behind
    would make the merge gate depend on a vendor without anyone changing a test.

    **Narrowed from "no live cell at all" when the first one was earned** (2026-08-02). The
    original wording forbade every live cell in the enclave, which read as the same protection
    and is not: a dispatched run resolves `CHOICE_ROLE` — `plan` — and nothing else. An `ask`
    cell is structurally unreachable from a dispatch, and role isolation is not assumed here,
    it is asserted by `test_a_cell_qualified_for_another_role_authorises_nothing`.

    The distinction matters because the broad form had a cost the narrow one does not: it made
    *earning a cell* and *shipping the enclave* mutually exclusive, so the first clean
    `make evals-live` run in this repository's history could not be recorded anywhere without
    turning a merge gate red. A gate that forbids the outcome it was written to protect gets
    deleted, and then nothing checks the thing that actually mattered.

    **Narrowed again 2026-08-07** to admit `judge`, which 043's relevance gate resolves on the
    ask path — see `SURFACE_ONLY_ROLES`. What still fails: a live cell in `plan`, `write` or
    `summarize`. `write` most of all — a model permitted to make changes is the one the enclave
    must never reach by accident.
    """
    chooser = build_chooser(FIXTURE_MODEL, recording=recording("vault_write", "vault_read"))
    request = ChoiceRequest(task=FIXTURE_TASK, permitted=FIXTURE_PERMITTED, step_index=0, attempt=0)
    # `Answer`, not a bare string, since 040 — and the RECORDING is unchanged. A bare name
    # in a recording is a choice with no arguments, so what this scripted sequence means is
    # exactly what it meant; what moved is the protocol's return type, which is 040's
    # declared seam change. The two are different claims and this row asserts the second.
    assert chooser.choose(request) == Answer("vault_write")

    variables = (ROOT / "infra/environments/dev/variables.tf").read_text()
    matrix = variables.split('variable "model_matrix_cells"', 1)
    assert len(matrix) == 2, "the dev environment no longer declares model_matrix_cells"

    # Each declared cell as a block, so `role` and `qualified_by` are read together rather than
    # searched for independently. Reading them apart is what made the original check coarse.
    blocks = re.findall(r"\{[^{}]*qualified_by[^{}]*\}", matrix[1])
    assert blocks, "no matrix cells parsed; this check would pass over an empty enclave"

    reachable = []
    for block in blocks:
        role = re.search(r'role\s*=\s*"([^"]+)"', block)
        if 'qualified_by = "live"' in block and role and role.group(1) not in SURFACE_ONLY_ROLES:
            reachable.append(role.group(1))

    assert not reachable, (
        f"a LIVE matrix cell ships in the dev enclave for {reachable}, a role a dispatched run "
        f"resolves ({CHOICE_ROLE!r} is the one it consults) — so a conformance row could reach a "
        f"vendor and the merge lane would fail for reasons unrelated to the code, which is how a "
        f"gate stops being run"
    )


def test_a_fixture_cell_without_a_recording_names_a_permitted_tool() -> None:
    """An absent recording has a defined answer; a SHORT one is still an error.

    The pair is the point, and the first enclave run of this feature is what set it. Every
    pre-020 dispatched row that invokes tools now consults a model, and requiring each to
    carry a script would have meant threading that script through the suspended-run index and
    the sweeper's resume dispatch — a control-plane column for a test affordance. So no
    script means "name the first permitted tool".

    A script that is *present* and runs out stays loud, because that is a different mistake:
    a row whose recording does not cover the run it was written for. Answering `""` there
    would end the run terminally while looking exactly like a model declining to act, and a
    row asserting a terminal run would pass for the wrong reason.
    """
    request = ChoiceRequest(task=FIXTURE_TASK, permitted=FIXTURE_PERMITTED, step_index=0, attempt=0)
    default = build_chooser(FIXTURE_MODEL, recording="")
    assert default.choose(request) == Answer("vault_read"), "sorted-first of the permitted set"
    assert default.choose(request) == Answer("vault_read"), "stable across asks"
    # NO ARGUMENTS, and that is the assertion rather than an incidental detail (040, FR-012):
    # the no-recording default names a tool it was not told about, so it has nothing to say
    # about what that tool should do. Answering with fabricated arguments would be the
    # fixture inventing an act.
    assert default.choose(request).arguments == {}

    short = build_chooser(FIXTURE_MODEL, recording=recording("vault_write"))
    assert short.choose(request) == Answer("vault_write")
    with pytest.raises(ChooserUnavailable) as excinfo:
        short.choose(request)
    assert excinfo.value.reason_code == "recording_exhausted"


def test_the_identifier_the_matrix_pins_is_the_one_called() -> None:
    """The join the matrix exists to keep tight.

    `provider/model@version` is enforced at parse precisely so what is pinned is what is
    called. A mapping that dropped the version would send every request to whatever the
    provider's default happened to be that week — auto-tracking under another name, which is
    what FR-011 of 013 forbade and what this identifier format was chosen to make
    inexpressible.
    """
    assert to_model_string("anthropic/claude-opus@5") == "anthropic:claude-opus-5"
    # The lane's own pin, whatever it currently is — 032 moved it to Sonnet and this line
    # asserted the Opus literal, which was the worked example above doing double duty. The
    # property is the derivation; the example row keeps the concrete mapping readable.
    assert to_model_string(LIVE_MODEL) == "anthropic:claude-sonnet-5"


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
    double = build_chooser(FIXTURE_MODEL, recording=recording("vault_read"))
    live = build_chooser(LIVE_MODEL)

    answers = {"double": double.choose(request), "live": live.choose(request)}
    for which, chosen in answers.items():
        # The NAME is what must be a well-formed choice from the permitted set. Since 040 an
        # answer also carries arguments, and those are the capability's business rather than
        # this row's — what the double and the provider must agree on is the shape of a
        # decision, which is the name.
        answer = chosen.name
        assert answer in FIXTURE_PERMITTED, (
            f"the {which} chooser answered {answer!r}, which is not a well-formed choice from "
            f"the permitted set {FIXTURE_PERMITTED} — the double and the provider no longer "
            f"agree in shape, so every lane using the double is asserting governance around "
            f"a stand-in for a decision it does not resemble"
        )
