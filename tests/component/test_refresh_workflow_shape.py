# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the weekly refresh runs the reviewed scripts and nothing else.

**Asserted against the parsed YAML, not against its prose.** Five features in this
repository have shipped a gate that matched a comment instead of code; a workflow file is
mostly comment, so the run steps are read from the parsed document and the reasoning is read
past. That is what `code_without_prose` exists for elsewhere and what `yaml.safe_load` does
natively here.

**What this row does NOT claim** (analyze P3): that no step touches the network. `checkout`
fetches, action resolution fetches, `setup-uv` downloads — "no network" is not assertable and
a row claiming it would either pass vacuously or fail on plumbing. What IS assertable, and
what matters, is that the only *repository code* this schedule executes is the two scripts a
human reviewed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "corpus-refresh.yml"

#: The scripts this schedule is permitted to execute. Adding a third is a reviewed act, and
#: this row is where that review is forced.
REVIEWED_SCRIPTS = ("infra/bin/corpus-sync", "infra/bin/skills-provenance")


@pytest.fixture(scope="module")
def workflow() -> dict[Any, Any]:
    """Keys are `Any` on purpose: PyYAML parses the bare `on:` key as the BOOLEAN True, so a
    `dict[str, Any]` annotation is a lie about this document's actual shape."""
    return dict(yaml.safe_load(WORKFLOW.read_text()))


@pytest.fixture(scope="module")
def steps(workflow: dict[Any, Any]) -> list[dict[str, Any]]:
    return list(workflow["jobs"]["refresh"]["steps"])


def test_it_runs_weekly_and_on_demand(workflow: dict[Any, Any]) -> None:
    # PyYAML parses the bare key `on` as the boolean True — a footgun worth naming, since a
    # row reading workflow["on"] would KeyError against a correct file.
    triggers: dict[str, Any] = workflow.get(True) or workflow.get("on") or {}
    assert "schedule" in triggers, "the refresh has no schedule — the half 024 left undone"
    assert "workflow_dispatch" in triggers, "no manual trigger; the dispatched row could not run"
    assert triggers["schedule"][0]["cron"].split()[-1] == "1", "not a weekly Monday cron"


def test_the_only_repository_code_it_runs_is_the_two_reviewed_scripts(
    steps: list[dict[str, Any]],
) -> None:
    """A schedule that could execute anything in the tree is a schedule nobody reviewed."""
    invoked = " ".join(step.get("run", "") for step in steps)

    for script in REVIEWED_SCRIPTS:
        assert script in invoked, f"the workflow does not run {script}"

    referenced = {
        token.strip("\"'`;|&()")
        for token in invoked.split()
        if token.strip("\"'`;|&()").startswith("infra/bin/")
    }
    assert referenced == set(REVIEWED_SCRIPTS), (
        f"the workflow runs repository scripts nobody reviewed for this schedule: "
        f"{sorted(referenced - set(REVIEWED_SCRIPTS))}"
    )


def test_its_permissions_are_exactly_what_the_proposal_needs(workflow: dict[Any, Any]) -> None:
    """Commit the pin, open the PR. Nothing else — and `write` is not the default, so an
    absent block would fail at `git push` rather than here."""
    assert workflow["permissions"] == {"contents": "write", "pull-requests": "write"}


def test_no_standing_credential_is_referenced(steps: list[dict[str, Any]]) -> None:
    """Principle IV, at the one place a weekly convenience would have bought an exception.

    A PAT in `secrets` is the obvious way to make the proposal's CI run. It is refused, and
    this row is what makes the refusal survive somebody's frustrated afternoon.
    """
    document = WORKFLOW.read_text()
    for forbidden in ("secrets.PAT", "secrets.GH_PAT", "secrets.PERSONAL", "secrets.TOKEN"):
        assert forbidden not in document, f"{forbidden} — a standing credential entered the tree"

    tokens = {
        value
        for step in steps
        for value in (step.get("env") or {}).values()
        if isinstance(value, str) and "token" in value.lower()
    }
    assert tokens <= {"${{ github.token }}"}, f"a non-default token is in use: {tokens}"


def test_the_proposal_explains_its_own_missing_checks(steps: list[dict[str, Any]]) -> None:
    """The consequence of refusing the PAT, carried to the reviewer rather than left as a
    mystery: a PR with no checks looks broken until you know why."""
    body = " ".join(step.get("run", "") for step in steps)

    assert "no checks" in body.lower()
    assert "standing credential" in body.lower(), "the refusal is stated, not just the symptom"
    assert "empty commit" in body.lower() or "reopen" in body.lower(), (
        "the reviewer is told the symptom but not the keystroke that fixes it"
    )


def test_one_standing_branch_rather_than_a_weekly_pile(steps: list[dict[str, Any]]) -> None:
    """analyze P2: dated branches stack proposals nobody closes."""
    body = " ".join(step.get("run", "") for step in steps)

    assert "chore/corpus-refresh" in body
    assert "--force" in body, "without a force-push the standing branch cannot be updated"
    assert "--state open" in body, (
        "gh pr view finds a MERGED PR on this head and then skips create — "
        "list open heads only, or the weekly pin never becomes a reviewable proposal"
    )
