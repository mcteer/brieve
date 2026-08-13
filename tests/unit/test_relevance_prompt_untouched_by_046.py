# SPDX-License-Identifier: Apache-2.0
"""046 U4 — sufficiency must not retune the 043 relevance subject-vs-sufficiency line."""

from __future__ import annotations

from adapters import anthropic_relevance


def test_subject_not_sufficiency_instruction_is_unchanged() -> None:
    system = anthropic_relevance._SYSTEM  # noqa: SLF001 — pin the sealed prompt text
    assert "Judge SUBJECT, not sufficiency." in system
    assert "only says where the full answer is documented" in system, (
        "043's subject-vs-sufficiency floor must stay; 046 adds a suite instead of retuning it"
    )
