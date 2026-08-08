# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the console's writer can authenticate, in the deployments that serve it.

**044 said the mechanism had no principal, fixed half of that, and closed it.** It granted
`authority_submit` on the records the console may write and attached the policy to the `api`
role — both true, both necessary, and neither sufficient. Nothing exchanged the workload
identity for a token and handed it to the submitter, so every request reached Vault with no
`X-Vault-Token` header.

**The consequence is the reason this row exists rather than a comment.** Vault answers an
unauthenticated write with 403, and 403 is how the fabric says *no*. So the console rendered
"the trust fabric denied this change" — a governance decision nobody made, indistinguishable
on the page from one somebody did. Found by an administrator endorsing a source and asking
whether anything had happened.

**Every existing row passed throughout**, and they were right to: the conformance rows pass a
token explicitly, because they are about the three outcomes rather than about how a surface
logs in. The gap lived in the assemblies, which no row constructs — the same place 026 and 027
put a collaborator into one surface and not the other, and the same lesson: *a green row proves
the mechanism, not that the running service can reach it.*
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Every assembly that builds a real submitter. Named rather than globbed, so a THIRD surface
#: gaining one is a deliberate addition here — 026 shipped a collaborator into one assembly and
#: not the other, and only a fourth analysis pass caught it.
ASSEMBLIES = (
    "src/surfaces/api/service.py",
    "src/surfaces/mcp/served.py",
)


def _submitter_call(source: str) -> ast.Call | None:
    """The `VaultAuthoritySubmitter(...)` expression in an assembly, if there is one."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = node.func
            if isinstance(name, ast.Name) and name.id == "VaultAuthoritySubmitter":
                return node
            if isinstance(name, ast.Attribute) and name.attr == "VaultAuthoritySubmitter":
                return node
    return None


def test_every_assembly_gives_the_submitter_a_way_to_authenticate() -> None:
    """The row. A submitter with neither a token nor a source cannot write anything.

    Asserted on the CALL rather than by starting the surface, because starting it needs Vault,
    Postgres and an attested identity — and a gate that only runs where all three exist is a
    gate that does not run.
    """
    missing = []
    for assembly in ASSEMBLIES:
        call = _submitter_call((ROOT / assembly).read_text())
        assert call is not None, f"{assembly} builds no submitter; remove it from ASSEMBLIES"

        supplied = {keyword.arg for keyword in call.keywords}
        if not supplied & {"token", "token_source"}:
            missing.append(assembly)

    assert not missing, (
        f"{missing} construct a submitter with no way to authenticate. Vault answers an "
        f"unauthenticated write with 403, and the console renders 403 as THE FABRIC REFUSED "
        f"THIS CHANGE — a governance decision nobody made, and indistinguishable on the page "
        f"from one somebody did."
    )


def test_no_assembly_holds_a_token_for_the_life_of_the_process() -> None:
    """Principle IV, at the one seam where a standing credential would be easiest to introduce.

    A `token=` in an assembly would be obtained once and held until the process ends. The
    parameter exists for the conformance rows, which supply a scripted one; a deployment passes
    a **source** and pays for a login per submit, which is what makes "zero standing
    credentials" true here rather than aspirational.
    """
    holding = []
    for assembly in ASSEMBLIES:
        call = _submitter_call((ROOT / assembly).read_text())
        assert call is not None
        if "token" in {keyword.arg for keyword in call.keywords}:
            holding.append(assembly)

    assert not holding, (
        f"{holding} hand the submitter a token rather than a way to get one, so the surface "
        f"holds a fabric credential for the life of the process"
    )


def test_the_source_is_the_same_brokered_identity_everything_else_uses() -> None:
    """Not a second authentication path to the trust fabric.

    `login()`'s own docstring says why it was extracted: *"a second class that authenticated
    its own way would be a second authentication path to the trust fabric, which is the shape
    Principle II forbids for tools and is no more attractive here."* This asserts the submitter
    uses that one rather than growing its own.
    """
    for assembly in ASSEMBLIES:
        call = _submitter_call((ROOT / assembly).read_text())
        assert call is not None
        source = next(k.value for k in call.keywords if k.arg == "token_source")

        assert isinstance(source, ast.Attribute) and source.attr == "login", (
            f"{assembly} gives the submitter something other than a workload login; a second "
            f"way into the fabric is the shape Principle II refuses"
        )
        assert isinstance(source.value, ast.Name) and source.value.id == "credentials", (
            f"{assembly} authenticates the submitter from something other than the brokered "
            f"identity every other collaborator in that file uses"
        )


def test_an_unauthenticated_submitter_is_reported_as_unavailable_not_refused() -> None:
    """The distinction the defect turned on, asserted on the behaviour rather than the wiring.

    A surface that cannot log in must not report a *refusal*. Denied sends an administrator to
    find an approver; unavailable sends them to an outage — and for three features the console
    would have sent them to look for a colleague who was never asked.
    """
    import pytest

    from surfaces.api.authority_submit import (
        AuthoritySubmitUnavailable,
        ConfigChange,
        VaultAuthoritySubmitter,
    )

    def cannot_log_in() -> str:
        raise RuntimeError("no attested identity")

    submitter = VaultAuthoritySubmitter(
        controlled_path="harness-authority/data/claim-mappings",
        token_source=cannot_log_in,
    )

    with pytest.raises(AuthoritySubmitUnavailable) as raised:
        submitter.submit_change(ConfigChange(record="ask-bindings", payload={}, requester="dan"))

    assert "never submitted" in str(raised.value)
