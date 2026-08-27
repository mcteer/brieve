# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the premise the Terraform declarations rest on (051, T012, row A19).

`terraform-style-guide` tells the agent to run `terraform fmt -recursive` and
`terraform validate` before committing. The Terraform pack declares both unsatisfiable, and
its pull requests say so. That sentence is true only while no registry tool offers either.

If someone adds one, this row fails here — beside the registry, where the change was made —
as well as at load via the stale-declaration check. Two places, because the fix is different
in each: withdraw the declaration, and stop printing the bullet.

**Scoped to the registry, not the repository.** `tests/evals_live/write_gates.py` really does
shell out to `terraform validate` as gate one of Write scoring. What does not exist is a tool
an authoring agent can call on the branch it is proposing, so the run's own artefacts were
never formatted or validated by the platform. The recommendation text says the narrower thing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from surfaces.toolset import PACKS_ROOT, build_registry, known_tools

#: What the vendored skill tells the agent to run, and what the pack therefore declares.
DECLARED_UNSATISFIABLE = ("terraform_fmt", "terraform_validate")


@pytest.mark.parametrize("capability", DECLARED_UNSATISFIABLE)
def test_the_capability_is_not_a_registry_tool(capability: str) -> None:
    registry, _ = build_registry(packs=["terraform"])
    assert capability not in known_tools(registry), (
        f"{capability!r} is now a registry tool. The Terraform pack still declares it "
        f"unsatisfiable, so every pull request tells a reviewer to do work the platform now "
        f"does. Withdraw the [[skills.unsatisfiable]] entry."
    )


def test_the_skill_really_does_recommend_them() -> None:
    """The declarations answer something the skill actually says.

    Without this the row above could pass forever against a skill that stopped recommending
    either — asserting the absence of tools nobody wanted.
    """
    skill = (PACKS_ROOT / "terraform" / "skills" / "terraform-style-guide" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "terraform fmt" in skill
    assert "terraform validate" in skill


def test_the_eval_lane_is_not_the_registry() -> None:
    """`terraform validate` is executed by this repository — and that is not the registry.

    This row exists because the claim nearly shipped unqualified. A pull request saying "this
    platform cannot run `terraform validate`" would be contradicted by the repository's own
    eval lane, which is the same overstated-evidence failure the feature exists to remove.
    """
    gates = Path(__file__).resolve().parents[2] / "evals_live" / "write_gates.py"
    source = gates.read_text(encoding="utf-8")
    assert re.search(r'"terraform",\s*"-chdir=', source), (
        "write_gates.py no longer shells out to terraform; the distinction this row "
        "documents may have changed and the pack's recommendation wording should be re-read"
    )
    assert "validate" in source
