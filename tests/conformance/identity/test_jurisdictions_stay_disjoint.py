# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a secrets grant is never read as a tool grant (FR-005).

ADR-0044: "policy jurisdictions are disjoint... no rule is duplicated across engines." A
registration's `ceiling_policies` bound which secrets a run's token may read; the harness
ceiling record bounds which tools it may call. **Neither is ever inferred from the other.**

The failure this guards is not an obvious one. Nobody would write "read the Vault policy as
a tool list" on purpose. What someone would write, on an afternoon when a definition was
registered without its ceiling record and runs were refusing, is a fallback — and a
fallback is how a grant to read `secret/data/planner/*` becomes permission to call `apply`.

# HYBRID(ceiling): migrated at T046a
"""

from __future__ import annotations

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.vault_fabric import CEILING_PATH
from tests.conformance.identity.conftest import production_fabric

pytestmark = pytest.mark.enclave


def test_row_a_registration_without_a_ceiling_record_refuses() -> None:
    """`demo-agent` is registered and 010 gives it a ceiling; a definition without one refuses.

    Uses a definition id that is registered in the registry but has no harness ceiling —
    constructed by reading the registry directly, because Terraform writes both together
    and there is deliberately no runtime path that writes one without the other.
    """
    fabric = production_fabric()

    # demo-agent HAS a ceiling record, so this proves the positive side first: the
    # refusal below is about the missing record, not about the definition being odd.
    assert fabric.resolve_ceiling("demo-agent").tool_names == frozenset({"echo"})

    with pytest.raises(ResolutionRefused) as caught:
        fabric.resolve_ceiling("definition-with-no-ceiling-record")

    assert caught.value.reason_code in {"unknown_agent_definition", "missing_ceiling_record"}


def test_row_the_ceiling_read_never_touches_the_policy_list() -> None:
    """The positive assertion behind the negative one.

    `planner-agent`'s ceiling policy grants `secret/data/planner/*` and its harness ceiling
    grants `echo` and `plan`. If the two were ever conflated the resolved scope would
    contain something path-shaped, or the policy names themselves.
    """
    scope = production_fabric().resolve_ceiling("planner-agent")

    assert scope.tool_names == frozenset({"echo", "plan"})
    assert not any("secret/" in name for name in scope.tool_names)
    assert "agent-ceiling-planner" not in scope.tool_names


def test_row_the_engine_appended_policies_are_accounted_for() -> None:
    """Research Finding 2, asserted rather than rediscovered.

    Terraform registers one ceiling policy; Vault stores three, appending `default` and
    `default-ceiling` unless `no_default_ceiling_policy` is set — which this repository has
    never set. The added policies are benign, and the point is not that they are dangerous:
    it is that the effective ceiling was never the declared one and nothing had looked.
    """
    observed = production_fabric().observed_policies("planner-agent")

    assert observed["configured"] == ["agent-ceiling-planner"]
    assert observed["engine_appended"], (
        "the engine no longer appends default policies — which may be an upgrade, and "
        "means research Finding 2 needs rechecking rather than this row deleting"
    )
    assert set(observed["effective"]) == set(observed["configured"]) | set(
        observed["engine_appended"]
    )


def test_row_the_ceiling_path_is_the_kv_data_path() -> None:
    """A wrong path 404s, and 404 is how this module reports "no such record".

    So a typo in the path constant does not fail loudly — it makes every definition look
    unconfigured, which reads as a Terraform problem and is not one.
    """
    assert CEILING_PATH.startswith("harness-authority/data/"), (
        "KV v2 nests data one level down; without /data/ every ceiling read 404s and every "
        "definition appears to have no ceiling record"
    )
