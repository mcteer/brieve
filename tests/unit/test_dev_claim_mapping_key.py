# SPDX-License-Identifier: Apache-2.0
"""The seeded dev claim-mapping key must match Python's `mapping_key`.

Terraform 1.15 rejects `\\x00` in quoted strings, so
`infra/modules/trust-fabric/dev_claim_mapping.tf` stores the digest as a literal.
A wrong literal seeds a record the verifier never reads, and browser sign-in then
looks like a broken deployment (`403 unmapped_claim`).
"""

from __future__ import annotations

from pathlib import Path

from core.identity.claims import ClaimMapping
from core.identity.mappings_store import mapping_key

DEV_OPERATOR = ClaimMapping(
    claim_name="permissions",
    claim_value="platform:operator",
    role="operator",
)

SEEDED_KEY = "operator-55ad4f49e3f06147"


def test_seeded_dev_mapping_key_matches_python() -> None:
    assert mapping_key(DEV_OPERATOR) == SEEDED_KEY


def test_terraform_seeds_the_python_key() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "infra"
        / "modules"
        / "trust-fabric"
        / "dev_claim_mapping.tf"
    ).read_text(encoding="utf-8")
    assignment = next(
        line for line in source.splitlines() if line.strip().startswith("dev_operator_mapping_key")
    )
    assert SEEDED_KEY in assignment
    assert r"\x00" not in assignment
