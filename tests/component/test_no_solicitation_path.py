# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — FR-014/SC-008: no run can ask a person for input mid-flight.

ADR-0049 removed the human-in-the-loop pause deliberately, and a conversational surface is
the single most likely place for it to come back — "just ask the user first" is so natural
to write here that it would not feel like a decision.

**The guarantee is an absence, so these rows assert an absence**, in the same shape as
`test_no_live_dependencies` and `test_surface_never_pauses`: no operation, no route, and
no code path exists by which a run solicits input. A behavioural row could only show that
no run *did* ask; these show that none *can*.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from core.run import RunState
from surfaces.mcp.operations import operations

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"

#: Words a solicitation mechanism would have to be called something like.
#:
#: Deliberately broad. A narrow list would miss the one someone actually writes, and a
#: false positive here costs a conversation about naming — which is the cheaper error.
SOLICITATION_WORDS = (
    "await_input",
    "await_user",
    "ask_user",
    "prompt_user",
    "request_input",
    "wait_for_reply",
    "wait_for_user",
    "human_input",
    "needs_input",
    "solicit",
)


def _python_sources() -> list[pathlib.Path]:
    return sorted(SRC.rglob("*.py"))


def test_no_operation_on_any_transport_solicits_input() -> None:
    """The catalogue is the whole set of things a caller can reach. None of them asks."""
    for op in operations():
        blob = f"{op.tool_name} {op.path} {op.description}".lower()
        for word in SOLICITATION_WORDS:
            assert word not in blob, (
                f"operation {op.tool_name!r} looks like a solicitation mechanism"
            )


def test_no_run_state_means_awaiting_a_person() -> None:
    """ADR-0049 removed PARKED. Nothing has quietly replaced it.

    SUSPENDED is the tempting substitute and is a different thing: it waits on a machine
    condition and the sweeper resumes it. A state meaning "waiting for a human" would be
    parking under a new name.
    """
    states = {s.value for s in RunState}
    assert "parked" not in states
    for state in states:
        assert "input" not in state
        assert "await" not in state


def test_no_source_file_defines_a_solicitation_function() -> None:
    """The structural half: no function anywhere in `src` is shaped like one."""
    offenders: list[str] = []
    for path in _python_sources():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            lowered = node.name.lower()
            for word in SOLICITATION_WORDS:
                if word in lowered:
                    offenders.append(f"{path.relative_to(SRC)}:{node.name}")

    assert offenders == [], f"solicitation-shaped functions exist: {offenders}"


def test_the_check_would_catch_one() -> None:
    """A positive control. An absence check nobody has seen fire proves nothing."""
    tree = ast.parse("def await_user_reply():\n    pass\n")
    found = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(word in node.name.lower() for word in SOLICITATION_WORDS)
    ]
    assert found == ["await_user_reply"]


def test_the_portal_has_no_route_that_returns_control_to_a_running_run() -> None:
    """A portal route that fed a person's answer back into a live run would be the pause.

    Every portal route either renders, or relays a catalogued operation that starts,
    stops, or reads. None of them writes into a run that is already going.
    """
    from surfaces.portal.app import create_portal
    from surfaces.portal.oidc import OidcClient
    from surfaces.portal.relay import ApiRelay

    app = create_portal(
        relay=ApiRelay(base_url="http://api.test"),
        oidc=OidcClient(
            issuer="https://idp.test/",
            client_id="portal",
            redirect_uri="http://testserver/callback",
            authorize_endpoint="http://idp.test/authorize",
            token_endpoint="http://idp.test/token",
        ),
    )
    paths = {getattr(route, "path", "") for route in app.routes}

    # The stop path is the ONLY one that reaches into a live run, and it ends it.
    reaching_into_runs = {p for p in paths if "/runs/" in p}
    assert reaching_into_runs == {"/runs/{run_id}/stop"}, (
        f"a portal route reaches into a running run other than to stop it: {reaching_into_runs}"
    )


@pytest.mark.parametrize("word", SOLICITATION_WORDS)
def test_no_template_offers_a_person_a_way_to_answer_a_run(word: str) -> None:
    """The rendered surface, too — the pause could be reintroduced as a form."""
    templates = pathlib.Path(__file__).resolve().parents[2] / "src/surfaces/portal/templates"
    for template in templates.rglob("*.html"):
        assert word not in template.read_text().lower(), (
            f"{template.name} contains {word!r}; a run must not be answerable"
        )
