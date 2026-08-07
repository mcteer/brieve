# SPDX-License-Identifier: Apache-2.0
"""V18 — the proposal carries its evidence, and a reviewer can answer three questions (042).

**SC-001 is the whole product**: reading only the pull request, a person can say what changed,
what it now permits, and on what basis. 041 proved the platform can open a proposal; this
decides whether opening one is useful.

**The impact section is platform-authored**, which is Principle IX rather than a style
preference: a model verdict may gate a step and never satisfies what evidence must show. So
the rows assert the section's content is arithmetic over Vault's answer, not prose about it.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.authoring.proposal import Proposal, ProposedFile
from core.authoring.request import RequestRefused
from surfaces.dispatch.policy_authoring import (
    UNSUPPORTED_DISCLOSURE,
    compose_policy_evidence,
    render_impact_evidence,
)

REAL = (
    "/validated-designs/vault-operating-guides-adoption/static-secrets"
    "#configure-policies-for-kv-secrets"
)
INVENTED = "/validated-designs/vault-operating-guides-adoption/does-not-exist#nowhere"

IMPACT: dict[str, Any] = {
    "measured_by": "vault",
    "truncated": False,
    "results": [
        {
            "path": "secret/data/payments/*",
            "current": ["read"],
            "proposed": ["create", "read", "update"],
            "granted": ["create", "update"],
            "revoked": [],
            "unanswered": False,
        },
        {
            "path": "secret/data/legacy/*",
            "current": ["read"],
            "proposed": [],
            "granted": [],
            "revoked": ["read"],
            "unanswered": False,
        },
    ],
}


def _resolves(path: str, anchor: str) -> bool:
    """The pin, scripted. The real corpus is exercised by the live legs."""
    return "does-not-exist" not in path


def _proposal(rationale: str = "") -> Proposal:
    return Proposal(
        target_repository="acme/vault-policies",
        branch="agent/policy-1",
        task="Grant the payments app write on its own KV prefix",
        files=[ProposedFile(path="policies/payments-app.hcl", body="", is_diff=True)],
        rationale=rationale,
    )


def test_row_v18_the_body_says_what_the_change_permits() -> None:
    """SC-001's second question, answerable from the rendered body alone."""
    proposal = compose_policy_evidence(
        proposal=_proposal(f"Per {REAL}, KV policies are configured per prefix."),
        impact=IMPACT,
        resolves=_resolves,
    )

    body = proposal.render()
    assert "### Measured impact" in body
    assert "**grants** create, update" in body
    assert "**revokes** read" in body


def test_row_v18_the_impact_section_is_arithmetic_not_prose() -> None:
    """Principle IX: a model verdict never satisfies what evidence must show.

    Every line here is derived from what `sys/capabilities` returned. If a future edit let the
    model write this section, the proposal would still render — and would be describing its
    own change, which is the reassurance the instrument exists to replace.
    """
    lines = render_impact_evidence(IMPACT)

    assert lines[0].startswith("Measured against the real product by `vault`")
    assert any("secret/data/payments/*" in line for line in lines)


def test_row_v18_an_unanswered_path_is_marked_unmeasured_not_unchanged() -> None:
    """The distinction the client and the handler both keep, carried through to the reviewer.

    A path rendered as "unchanged" when Vault did not answer would tell a reviewer the change
    is safe there. It says nothing of the kind.
    """
    lines = render_impact_evidence(
        {
            "measured_by": "vault",
            "results": [
                {"path": "secret/data/x", "granted": [], "revoked": [], "unanswered": True}
            ],
        }
    )

    assert any("not answered" in line and "unmeasured" in line for line in lines)
    # The RENDER pattern, not the word: the warning line legitimately contains "unchanged"
    # in the phrase "must not be read as unchanged", and asserting on the bare word made this
    # row fail on its own correct output.
    assert not any("— unchanged (" in line for line in lines)


def test_row_v18_a_truncated_measurement_says_the_rest_is_unmeasured() -> None:
    """029's lesson at the reviewer's end: a silent bound reads as completeness."""
    lines = render_impact_evidence({**IMPACT, "truncated": True})

    assert any("unmeasured, not unchanged" in line for line in lines)


def test_row_v18_resolving_citations_are_listed() -> None:
    """SC-001's third question — on what basis."""
    proposal = compose_policy_evidence(
        proposal=_proposal(f"See {REAL} for the recommended shape."),
        impact=IMPACT,
        resolves=_resolves,
    )

    assert any(REAL in line for line in proposal.evidence)
    assert UNSUPPORTED_DISCLOSURE not in proposal.disclosures


def test_row_v18_reasoning_that_resolves_nothing_is_disclosed_not_blocked() -> None:
    """FR-012 — declining to CLAIM grounding, rather than declining to propose.

    Refusing outright would make the platform useless for any change the corpus does not
    happen to discuss; passing invented citations off as grounding is the confabulation the
    whole answering surface exists to prevent. The disclosure is the honest third option.
    """
    proposal = compose_policy_evidence(
        proposal=_proposal(f"See {INVENTED}."), impact=IMPACT, resolves=_resolves
    )

    assert UNSUPPORTED_DISCLOSURE in proposal.disclosures
    assert UNSUPPORTED_DISCLOSURE in proposal.render()


def test_row_v18_a_proposal_with_no_impact_is_refused() -> None:
    """FR-008 at the publishing end, and the pair with V13.

    V13 refuses when the measurement cannot be taken. This refuses when it simply is not
    attached — the same failure arriving through a composition path instead of an outage.
    """
    with pytest.raises(RequestRefused) as raised:
        compose_policy_evidence(proposal=_proposal("x"), impact=None, resolves=_resolves)

    assert raised.value.reason_code == "impact_unavailable"


def test_row_v18_no_secret_value_or_trust_fabric_body_reaches_the_body() -> None:
    """[GATE:no-secret-leak] SC-006, asserted over the composed body rather than claimed.

    The structural guarantee is upstream — `vault_policy_read` never reads a protected body,
    and the impact evidence is capability names — so this row is the check that the two
    guarantees actually meet in the artefact a person receives.
    """
    proposal = compose_policy_evidence(
        proposal=_proposal(f"Per {REAL}, scope the policy to its own prefix."),
        impact=IMPACT,
        resolves=_resolves,
    )

    body = proposal.render()
    assert "capabilities = " not in body, "a policy BODY reached the proposal"
    assert "agent-ceiling" not in body
    assert not any(token in body for token in ("hvs.", "s.", "root-token"))


def test_the_evidence_section_precedes_the_limits() -> None:
    """Ordering is 041's rule and it holds: nothing follows the limits and reframes them."""
    body = compose_policy_evidence(
        proposal=_proposal("x"), impact=IMPACT, resolves=_resolves
    ).render()

    assert body.index("### Measured impact") < body.index("### Limits")
