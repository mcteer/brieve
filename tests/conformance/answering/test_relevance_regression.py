# SPDX-License-Identifier: Apache-2.0
"""R9-R12 — nothing regresses, and the decision is inspectable (043, US2/US3).

**R10 is the row that would fail if the fix were product-scoping**, and that is its reason to
exist. Scoping a pack's answers to its own product's documents would close gap 0g and undo 035,
which widened the corpus so the platform could answer architecture questions. A fix that made
the platform single-product would trade the defect for its opposite, and this row is what makes
that trade visible instead of silent.

**R9 is asserted as a diff from the merge-base, not from `main`.** `main` moves during
implementation, and this estate has already recorded what a wrong baseline reports: false
parity.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from core.answering.answer import ANSWERED, answer_question
from core.answering.corpus import Corpus, Document
from tests.harness.fixture_relevance import FixtureRelevanceJudge

ROOT = Path(__file__).resolve().parents[3]

#: The eval CASE files this feature promised not to touch (FR-004, SC-003).
EVAL_CASES = "packs"

#: Routes to GUIDANCE. The gate is guidance-only by design (research R7): an estate answer's
#: claims cite the asker's own records, already bounded by role scope and 029's window, and its
#: relevance failure mode is routing rather than corpus breadth. A row that asked an
#: estate-shaped question would find no MODEL_GATE and be right to.
GUIDANCE_QUESTION = "How does an AI agent obtain an identity with Vault?"


def _merge_base() -> str:
    """The baseline. Not `main` — it moves, and a moving baseline reports false parity."""
    result = subprocess.run(
        ["git", "merge-base", "main", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def test_row_r9_no_answering_eval_case_was_edited() -> None:
    """R9 — the promise, asserted as a diff rather than as a claim (FR-004, SC-003).

    A fix that bought its decline by editing the cases would pass every other row in this
    feature. This is the one that makes that impossible to do quietly.
    """
    base = _merge_base()
    assert base, "no merge-base against main; the baseline this row needs does not exist"

    changed = subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD", "--", f"{EVAL_CASES}/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()

    edited_cases = [path for path in changed if path.endswith(".toml") and "/evals/" in path]
    assert not edited_cases, (
        f"{edited_cases} are answering eval cases and this feature edited them. The failing "
        f"case caught a real regression; editing it is the gate tuning this estate refuses."
    )


def _corpus() -> Corpus:
    """Two products' documents, which is the state 035 created and 0g exposed."""
    vault = "/validated-designs/vault-operating-guides-adoption/monitoring-and-observability"
    boundary = "/validated-designs/boundary-operating-guides-standardization/audit-logs"
    return Corpus(
        digest="digest-r10",
        documents={
            vault: Document(
                path=vault,
                url=f"https://developer.hashicorp.com{vault}",
                digest="d1",
                anchors=frozenset({"audit-device-metrics"}),
                sections={"audit-device-metrics": "Vault audit device metrics."},
            ),
            boundary: Document(
                path=boundary,
                url=f"https://developer.hashicorp.com{boundary}",
                digest="d2",
                anchors=frozenset({"audit-log-streaming"}),
                sections={"audit-log-streaming": "Boundary audit log streaming."},
            ),
        },
    )


class _CrossProductProvider:
    """One claim per product — the shape 035 widened the corpus to make possible."""

    def answer(self, question: str, corpus: Corpus, context: str = "") -> list[dict[str, Any]]:
        paths = sorted(corpus.documents)
        return [
            {
                "statement": f"A claim grounded in {path}.",
                "citations": [{"path": path, "anchor": next(iter(corpus.documents[path].anchors))}],
            }
            for path in paths
        ]


def test_row_r10_a_genuinely_cross_product_answer_survives() -> None:
    """R10 — the row that fails if the fix is product-scoping (FR-005, SC-004).

    The judge affirms both claims, so the only thing that could drop one is the platform
    deciding a document's product disqualifies it. Nothing in this feature does that, and this
    row is how it stays true.
    """
    answer = answer_question(
        question="How should audit logging be approached across our HashiCorp estate?",
        corpus=_corpus(),
        provider=_CrossProductProvider(),
        relevance=FixtureRelevanceJudge(),
    )

    assert answer.disposition == ANSWERED
    assert len(answer.claims) == 2, "an affirmed cross-product answer must keep both claims"

    cited = {citation.path for claim in answer.claims for citation in claim.citations}
    products = {path.split("/")[2].split("-")[0] for path in cited}
    assert len(products) == 2, (
        f"the surviving citations span {products}; a fix that narrowed to one product would "
        f"close gap 0g by undoing 035, which is the defect traded for its opposite"
    )
    assert answer.irrelevant == ()


def test_row_r11_the_gate_writes_one_model_gate_per_answered_ask() -> None:
    """R11 — MODEL_GATE, ordered before the outcome it produced (FR-016, SC-010)."""
    from fastapi.testclient import TestClient

    from tests.harness.api_fixtures import (
        available_credential,
        qualified_ask_authority,
        surface_under_test,
    )

    real_path = "/validated-designs/vault-operating-guides-adoption/initial-configuration"

    class _Surviving:
        def answer(self, question: str, material: Any, context: str = "") -> list[dict[str, Any]]:
            return [
                {
                    "statement": "Vault's initial configuration covers enabling an audit device.",
                    "citations": [{"path": real_path, "anchor": "enabling-an-audit-device"}],
                }
            ]

    surface = surface_under_test(
        ask_provider=_Surviving(),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(model="anthropic/claude-opus@5"),
        credential_source=available_credential(),
        relevance_judges=lambda cell: FixtureRelevanceJudge(),
    )

    TestClient(surface.app).post(
        "/ask",
        json={"question": GUIDANCE_QUESTION},
        headers=surface.bearer(),
    )

    entries = surface.audit.all_entries()
    kinds = [str(entry.event_type) for entry in entries]
    assert "model_gate" in kinds, "every relevance judgement writes a MODEL_GATE"
    assert kinds.index("model_gate") < kinds.index("ask_answered"), (
        "the gate is recorded BEFORE the outcome it produced — a reader meets the decision "
        "before its consequence (031's ordering)"
    )

    gate = next(e for e in entries if str(e.event_type) == "model_gate").payload
    assert gate["gate"] == "relevance"
    assert "kept_count" in gate and "irrelevant_count" in gate
    assert not any(isinstance(value, str) and len(value) > 200 for value in gate.values()), (
        "the gate payload carries counts and identities, never statements — the ask record "
        "already carries the claims once, and a second copy is a second place to redact"
    )


def test_row_r12_a_declined_ask_is_inspectable_from_its_records() -> None:
    """R12 — what was considered, on which ground, and which model judged (FR-006, SC-007)."""
    from fastapi.testclient import TestClient

    from tests.harness.api_fixtures import (
        available_credential,
        qualified_ask_authority,
        surface_under_test,
    )

    real_path = "/validated-designs/vault-operating-guides-adoption/initial-configuration"

    class _OffSubject:
        def answer(self, question: str, material: Any, context: str = "") -> list[dict[str, Any]]:
            return [
                {
                    "statement": "A true, cited claim about something else entirely.",
                    "citations": [{"path": real_path, "anchor": "enabling-an-audit-device"}],
                }
            ]

    surface = surface_under_test(
        ask_provider=_OffSubject(),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(model="anthropic/claude-opus@5"),
        credential_source=available_credential(),
        relevance_judges=lambda cell: FixtureRelevanceJudge(affirm_none=True),
    )

    TestClient(surface.app).post(
        "/ask",
        json={"question": GUIDANCE_QUESTION},
        headers=surface.bearer(),
    )

    entries = surface.audit.all_entries()
    ask = next(e for e in entries if str(e.event_type) == "ask_answered").payload
    gate = next(e for e in entries if str(e.event_type) == "model_gate").payload

    assert ask["disposition"] == "declined"
    assert ask["declined_reason"], (
        "the RECORD must carry why, not only the response — a reason that exists in the reply "
        "and not in the trail is invisible to an auditor"
    )
    assert "cover" in ask["declined_reason"], "and it names the ground: not covered"
    assert gate["irrelevant_count"] == 1 and gate["kept_count"] == 0
    assert gate["model"], "which model judged is part of the record, not an inference"
