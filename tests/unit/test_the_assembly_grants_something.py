# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the production assembly must give the verifier a source of grants.

`resolve_roles` treats an empty mapping set as "grant nothing", which is right. The
consequence is that a verifier built without mappings refuses **every** authenticated
request — and that is precisely how `service.py` built one. The surface was correct, the
verifier was correct, the mapping store did not exist, and no test could see it: every
component test passes its own mappings in, so the only broken assembly was the one
nobody constructed under test.

Asserted over the source rather than by calling `build()`, because `build()` opens Vault
and Postgres connections and runs migrations. A unit gate that needed the enclave would
not run in the fast lane, which is the lane that has to catch this. The narrowness is the
point: this does not check that the mappings are *correct*, only that the assembly
reaches for some. That is the whole distance between "refuses everyone" and "works".
"""

from __future__ import annotations

import ast
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[2] / "src" / "surfaces" / "api" / "service.py"


def _verifier_call(tree: ast.AST) -> ast.Call:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name == "TokenVerifier":
                return node
    raise AssertionError(
        "the API assembly constructs no TokenVerifier. If the surface stopped "
        "authenticating anyone, that is a much larger change than this gate."
    )


def test_the_api_assembly_gives_the_verifier_a_source_of_mappings() -> None:
    call = _verifier_call(ast.parse(SERVICE.read_text()))
    passed = {kw.arg for kw in call.keywords}

    assert passed & {"mappings", "mappings_source"}, (
        "the production TokenVerifier is built with neither `mappings` nor "
        "`mappings_source`, so `resolve_roles` returns empty and this surface refuses "
        "every authenticated request with `unmapped_claim` — for any identity provider, "
        "however correctly configured. This is what shipped before the mapping store "
        "existed, and it was invisible because every component test supplies its own."
    )


def test_the_api_assembly_does_not_pin_its_grants_in_code() -> None:
    """A literal list here would put role grants outside the quorum gate.

    Not a style objection. `ClaimMapping` changes are an authority change (ADR-0016), and
    a list in this file is granted by whoever can merge rather than by whoever can
    approve — which is the escalation path the gate exists to close.
    """
    call = _verifier_call(ast.parse(SERVICE.read_text()))
    literal = next((kw for kw in call.keywords if kw.arg == "mappings"), None)

    assert literal is None, (
        "the production assembly pins claim-to-role mappings in source. Grants belong "
        "behind the Control Group that governs them; read them from the trust fabric "
        "instead (`VaultClaimMappings`)."
    )


def test_the_api_assembly_tries_the_human_verifier_first() -> None:
    """Order is load-bearing when one issuer serves both kinds, which is the common case.

    A workload verifier admits a person's token — it must, because a bare Nomad workload
    identity carries no machine marker either, so demanding one would refuse every genuine
    federated workload. With Auth0, Okta, Ping or Entra all serving `client_credentials`
    and `authorization_code` from one issuer, a person's token therefore satisfies both
    members and the first one tried wins.

    Built the other way round the surface still authenticates everyone correctly and
    records every person as a machine, which is the failure that leaves no symptom.
    """
    tree = ast.parse(SERVICE.read_text())
    kinds = [
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "SubjectKind"
    ]

    assert kinds, "the assembly names no SubjectKind, so nothing decides what a token is"
    assert kinds[0] == "HUMAN", (
        f"the API assembly reaches for {kinds[0]} before HUMAN. With a shared issuer the "
        f"first verifier that accepts a token wins, and a workload verifier accepts a "
        f"person's — so this order records people as machines."
    )
