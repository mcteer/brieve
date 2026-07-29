# SPDX-License-Identifier: Apache-2.0
"""GATE:determinism — FR-012 (004) and FR-016 (005), asserted rather than assumed.

**The rule changed shape in 005 and this file is where that is encoded.** Every feature
before it asserted "no operated service"; durable execution *requires* Vault and
Postgres, because they are components this project deploys and substituting them would
mean the guarantees ship unproven against what they actually run on.

What survives is narrower, and still absolute: no live model provider, no live
managed-product API, and no disruption simulated by terminating real infrastructure.
Written as two lists rather than one so the distinction is visible — a future reader
must be able to tell "this client is banned everywhere" from "this client is allowed
only where it talks to our own enclave".

Two checks, because neither alone is sufficient:

(a) **Direct-import scan** over test module *source*. Deliberately not a
    ``sys.modules`` check: ``pydantic-ai-slim`` pulls an HTTP client in
    transitively, so a runtime check would fail on every adapter test while
    proving nothing about what the tests themselves reach for.

(b) **Model resolution.** Adapter tests must build agents with stub models. This
    is what actually prevents a live call; (a) cannot, since a live call needs no
    new import if a client is already reachable.

Known limit: this catches *reaching for* a live client, not a call made through
one already imported. Closing that needs a socket-blocking plugin, which adds a
dependency to a regulated tree — escalate only if a live call ever slips through
(specs/004-primary-adapter/research.md).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from tests.harness.adapter_fixtures import scripted_tool_model

TESTS_ROOT = Path(__file__).resolve().parents[1]

#: Banned everywhere, without exception: a live model provider or managed-product API.
#: These are outside our boundary, so a test reaching for one is reaching outside the
#: system under test (FR-016, SC-010).
DENIED_EVERYWHERE = frozenset(
    {
        "openai",
        "anthropic",
        "google.generativeai",
        "boto3",
    }
)

#: Generic HTTP and Vault clients. Banned in ordinary tests, permitted only in the
#: modules below, which talk to the local enclave — our own Vault and Postgres. A
#: blanket ban here would now be *wrong*, and would push the durability rows back to
#: fakes, which is the substitution this project rejects.
DENIED_OUTSIDE_ENCLAVE_PATHS = frozenset(
    {
        "httpx",
        "httpcore",
        "requests",
        "urllib.request",
        "urllib3",
        "aiohttp",
        "hvac",
    }
)

#: Exactly the modules that may reach the enclave. Deliberately an explicit list rather
#: than a directory glob: adding a module here should be a visible decision.
ENCLAVE_PATHS = frozenset(
    {
        # The conformance conftest is NO LONGER here. It used to reach Vault over HTTP
        # with a development token; it now obtains credentials the way the harness does,
        # by presenting a workload identity, so it needs no HTTP client of its own.
        #
        # The list shrank because the reason for an entry went away. An allowlist that
        # only ever grows is not an allowlist.
        "component/test_resume_cross_process.py",
        # 013's host rows, same posture as 011's divergence rows below: a host process
        # holds no attested identity — a property the platform is built on — so the
        # matrix-grant rows read Vault as the OPERATOR, and the pack-dispatch rows drive
        # the scheduler, which only a host process legitimately can.
        "conformance/identity/test_matrix_is_readable.py",
        "conformance/identity/test_pack_tools_dispatch.py",
        # 011's divergence rows read the audit trail as an OPERATOR, with a token.
        #
        # **This is not the entry that was removed above, arriving back.** That one used a
        # development token in a lane where an attested identity was available, and the
        # fix was to use the identity. These rows run in the HOST lane, which has no
        # workload identity at all — that is the property the lane exists to preserve —
        # and they belong there because they drive the scheduler, which the allocation
        # cannot. So the choice is an operator token or a row that cannot run where the
        # thing it checks happens. `OperatorCredentials` in that conftest is test-only and
        # deliberately not a `core` class, so the fallback stays out of production reach.
        "conformance/identity/conftest.py",
        # Talks to the control-plane Vault to exercise Control Groups (007). There is no
        # fake: one that always approves proves the caller can proceed, one that never
        # approves proves it handles denial, and neither proves the gate holds.
        "harness/vault_control_groups.py",
        # Talks to the local scheduler to prove a run start actually dispatches (008).
        # There is no useful fake: `InProcessDispatcher` proves the surface returns a
        # handle without blocking and proves nothing about dispatch — which is exactly
        # what this feature shipped at first, with NomadDispatcher exercised by no test
        # and the job it dispatches to nonexistent.
        "conformance/api/test_run_start_does_not_block.py",
        # Watches the scheduler place a real allocation and reports what it did (010).
        # There is no fake, and the reason is the point of the row: it exists to prove the
        # entrypoint CONSTRUCTS the production fabric and resolves through it. Anything
        # in-process would be asserting that the code it just imported does what it says,
        # which every other row in the feature already covers.
        "conformance/identity/test_dispatched_end_to_end.py",
        # Presents an AGENT's credential to the trust fabric to prove it is refused (010).
        # A fake cannot express this: the assertion is that VAULT denies, and a double
        # denying proves only that we wrote a double that denies.
        "conformance/identity/test_fabric_unreachable_from_a_tool.py",
        # Watches an allocation reach a terminal state before comparing the run index
        # against the audit trail (011). The wait is the row's substance: the two writes
        # are minutes apart on a cold dispatch, and comparing inside that window would
        # flake at exactly the cadence cold allocations occur.
        "conformance/identity/test_run_index_and_trail_agree.py",
    }
)


def _imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_no_test_module_imports_a_live_model_or_product_client() -> None:
    """No exceptions, no allowlist. These are outside our boundary."""
    offenders: list[str] = []
    for path in TESTS_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _imported_names(tree):
            if name in DENIED_EVERYWHERE or name.split(".")[0] in DENIED_EVERYWHERE:
                offenders.append(f"{path.relative_to(TESTS_ROOT)}: {name}")
    assert not offenders, (
        f"test modules reach for a live model or product API: {offenders}. "
        "Those are outside our boundary and are faked (FR-016, SC-010)."
    )


def test_http_clients_appear_only_where_they_reach_our_own_enclave() -> None:
    offenders: list[str] = []
    for path in TESTS_ROOT.rglob("*.py"):
        relative = str(path.relative_to(TESTS_ROOT))
        if relative in ENCLAVE_PATHS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for name in _imported_names(tree):
            if (
                name in DENIED_OUTSIDE_ENCLAVE_PATHS
                or name.split(".")[0] in DENIED_OUTSIDE_ENCLAVE_PATHS
            ):
                offenders.append(f"{relative}: {name}")
    assert not offenders, (
        f"HTTP clients outside the enclave paths: {offenders}. Reaching the local Vault "
        "or Postgres is expected in 005; reaching anything else is not. If this module "
        "genuinely talks to the enclave, add it to ENCLAVE_PATHS as a visible decision."
    )


def test_no_test_terminates_real_infrastructure() -> None:
    """SC-010: disruption is simulated, never inflicted.

    The cross-process scenario spawns an interpreter, which is fine — restarting a test
    process is not terminating infrastructure. Killing a container or a Nomad job is.
    """
    # Assembled so this module does not itself contain the banned literals — the same
    # trick tests/unit/test_core_import.py uses, and for the same reason.
    banned = (
        "docker " + "stop",
        "docker " + "kill",
        "docker " + "rm",
        "nomad job " + "stop",
        "SIG" + "KILL",
        "pk" + "ill",
    )
    offenders: list[str] = []
    for path in TESTS_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in banned:
            if needle in text:
                offenders.append(f"{path.relative_to(TESTS_ROOT)}: {needle}")
    assert not offenders, (
        f"tests terminate real infrastructure: {offenders}. Disruption is simulated "
        "in-process (FR-016)."
    )


def test_scripted_model_is_a_stub_not_a_provider() -> None:
    """The fixture model resolves to a local function, not a provider client."""
    model = scripted_tool_model([("echo", {})])
    assert type(model).__name__ == "FunctionModel"
    assert "function" in type(model).__module__


@pytest.mark.anyio
async def test_scripted_model_needs_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run completes with every provider credential removed from the environment."""
    for var in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "VAULT_TOKEN",
    ):
        monkeypatch.delenv(var, raising=False)

    from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture

    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        registry_tools={"echo": handler},
    )

    await agent.run("go", deps=deps)

    assert handlers["echo"].call_count == 1
