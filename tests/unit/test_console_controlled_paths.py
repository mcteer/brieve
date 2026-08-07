# SPDX-License-Identifier: Apache-2.0
"""C6 — the console's records are gated, and the mechanism keeps its principal (044, T002).

**Two properties, and the second is the one 044 exists because of.**

`C6` is completeness: every record the console may write appears in the Control Group's path
list, asserted against the module's own lists rather than trusted. Same shape as 042's V6 —
the list is hand-written and *that it is complete* is a merge gate.

**The R1 guard is different in kind.** `authority_submit.py` has shipped since 007 and was
never exercisable in a deployment: no policy granted write on any `harness-authority` path,
and `authority_change` — the Control-Group-gated write policy — was attached to no role. The
conformance rows passed because they run with an operator token. A grant that exists in a
`.tf` file and is attached to nothing is exactly the "correct, tested, wired to nothing"
shape 041 spent a feature closing, so the attachment is asserted rather than assumed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "infra" / "modules" / "trust-fabric"


def _hcl(name: str) -> str:
    return (MODULE / name).read_text()


def _list_literal(text: str, name: str) -> list[str]:
    """The string entries of a named HCL list local."""
    start = text.index(f"{name} = [")
    body = text[start : text.index("\n  ]", start)]
    return re.findall(r'"([^"]+)"', body)


def _policy_block(text: str, resource: str) -> str:
    start = text.index(f'resource "vault_policy" "{resource}"')
    return text[start : text.index("\n}", start)]


def _granted_paths(block: str) -> list[str]:
    return re.findall(r'^\s*path\s+"([^"]+)"\s*\{', block, re.M)


def test_row_c6_every_record_the_console_writes_is_gated() -> None:
    """C6 — completeness of the gate list against the grant it is meant to cover.

    A record the console can write and the Control Group does not name is FR-005 being false
    while reading as true: wherever a quorum IS configured, the change applies directly and
    the console reports it as governed.
    """
    gated = _list_literal(_hcl("control-groups.tf"), "console_controlled_paths")
    granted = _granted_paths(_policy_block(_hcl("authority-submit.tf"), "authority_submit"))

    # The grant is written with `${vault_mount...path}` interpolation; the gate list uses the
    # same expression, so compare on the record suffix rather than on the rendered mount.
    def _suffix(path: str) -> str:
        return path.split("}/", 1)[-1] if "}/" in path else path

    missing = sorted({_suffix(p) for p in granted} - {_suffix(p) for p in gated})

    assert not missing, (
        f"{missing} are writable by the console and absent from `console_controlled_paths`. "
        f"Where a quorum is configured, a change to one of them would apply directly while "
        f"the console reported it as awaiting approval — FR-005 false and reading as true."
    )


def test_row_c6_the_gate_list_names_nothing_the_console_cannot_write() -> None:
    """The other direction. A gated path with no grant behind it is a rule about nothing.

    Without this, C6 could be satisfied forever by a list that grew and a grant that did not
    — and the completeness it asserts would drift into decoration.
    """
    gated = _list_literal(_hcl("control-groups.tf"), "console_controlled_paths")
    granted = _granted_paths(_policy_block(_hcl("authority-submit.tf"), "authority_submit"))

    def _suffix(path: str) -> str:
        return path.split("}/", 1)[-1] if "}/" in path else path

    orphaned = sorted({_suffix(p) for p in gated} - {_suffix(p) for p in granted})

    assert not orphaned, f"{orphaned} are gated and nothing can write them; the gate is inert"


def test_the_mechanism_has_a_principal() -> None:
    """The R1 regression guard, and the finding that reshaped this feature.

    `authority_submit.py` shipped in 007. Until 044 it had no deployed principal: no policy
    granted write on any `harness-authority` path and the gated policy was attached to no
    role, so the request-and-decide path worked only under an operator token supplied by a
    test. This asserts the attachment, because a policy nothing holds is a policy nothing
    can exercise.
    """
    auth = _hcl("auth.tf")
    api_role = auth[auth.index('role_name               = "api"') :]
    api_role = api_role[: api_role.index("\n}")]

    assert "vault_policy.authority_submit.name" in api_role, (
        "the api role does not carry `authority_submit`. The submitter would then request "
        "changes with no authority to make them — which is the state 007 through 043 shipped "
        "in, and the reason this feature's first task is infrastructure rather than a page."
    )


def test_the_gated_variant_is_attached_when_a_quorum_is_configured() -> None:
    """Ungated is a legitimate development posture; ungated-while-a-quorum-exists is not.

    The conditional attachment is what makes the estate's posture follow its own
    configuration rather than following whoever last edited the role.
    """
    auth = _hcl("auth.tf")
    api_role = auth[auth.index('role_name               = "api"') :]
    api_role = api_role[: api_role.index("\n}")]

    assert "authority_submit_gated" in api_role
    assert "control_groups_enabled" in api_role, (
        "the gated policy must attach conditionally on the quorum being configured, so a "
        "deployment that sets one gets the gate without a second edit"
    )


def test_the_console_cannot_write_the_records_this_feature_left_in_terraform() -> None:
    """Scope, asserted rather than trusted (spec Assumptions).

    Ceilings and the matrix decide what agents may do and which models are qualified. This
    feature deliberately leaves them as estate governance, and a glob over the mount would
    have handed both over silently — which is why the grant enumerates.
    """
    granted = _granted_paths(_policy_block(_hcl("authority-submit.tf"), "authority_submit"))

    for out_of_scope in ("harness-ceilings", "model-matrix", "protected-policies", "policies/"):
        assert not any(out_of_scope in path for path in granted), (
            f"the console can write {out_of_scope!r}, which this feature scoped out. A "
            f"widening here is a governance change nobody requested."
        )
    assert not any(path.rstrip("*").endswith("data/") for path in granted), (
        "a glob over the mount grants every record in it, including the ones above"
    )
