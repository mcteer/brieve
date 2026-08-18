# SPDX-License-Identifier: Apache-2.0
"""The dev operator role must be able to start Build (047).

Manufacture is role ∩ ceiling ∩ task. `authoring-agent`'s ceiling already names the
authoring trio; the operator binding did not, so the only role the dev IdP grants could
never start a Build. This file is the pin so the next apply cannot drop them silently.
"""

from __future__ import annotations

from pathlib import Path

from surfaces.toolset import AUTHORING_VOCABULARY

ROOT = Path(__file__).resolve().parents[2]
VARS = ROOT / "infra" / "environments" / "dev" / "variables.tf"


def test_operator_role_binding_names_the_authoring_trio() -> None:
    text = VARS.read_text(encoding="utf-8")
    start = text.index('variable "role_bindings"')
    default = text[start:]
    op = default.index('"operator" = {')
    block = default[op : default.index("\n    }", op)]
    missing = sorted(name for name in AUTHORING_VOCABULARY if name not in block)
    assert not missing, (
        f"operator role binding omits {missing}; Build then refuses manufacture for the "
        "dev IdP's only role even though authoring-agent's ceiling already names them"
    )
