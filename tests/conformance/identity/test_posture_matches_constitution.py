# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the deployed posture does not contradict the constitution's text.

**Scoped to what a check can actually see**, and the scoping is the honest part. Three claims live
in Principle IV's amended sentences, and they are observable in three different places:

1. *"exactly three named exceptions"* — text, checkable here.
2. *"static API keys are prohibited as workload credentials"* — a **config** property: no jobspec
   hands a vendor key to a workload as an environment variable. Greppable in HCL, checkable here.
3. *"never persisted by any workload"* — a **runtime** property. A workload writing a fetched key
   to disk is invisible to a config grep, and asserting it here would be a check that looks like it
   covers the requirement while covering none of it. That half lives where it is observable: at the
   trail and the response body, in
   `tests/conformance/answering/test_model_credential_posture.py`.

Stating the split is the point. A conformance row that quietly covers two thirds of a requirement
is worse than two rows that each say what they cover, because the gap is invisible from the green.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONSTITUTION = ROOT / ".specify/memory/constitution.md"
JOBS = ROOT / "infra/jobs"

#: Names a vendor key wears in a jobspec. Not exhaustive by construction — a check like this can
#: only catch the shapes somebody would actually reach for, and the runtime rows are what stand
#: behind it.
VENDOR_KEY_NAMES = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "EVAL_PROVIDER_API_KEY",
)


def _principle_iv() -> str:
    """Principle IV's own text, without the Sync Impact Report's commentary about it.

    The report at the top of the file *quotes* both the old and the new wording, so a check
    matching the whole document would find "exactly one named exception" in the changelog and
    report a contradiction that does not exist — a check reading prose about code instead of the
    code, one genre over.
    """
    text = CONSTITUTION.read_text()
    body = text.split("-->", 1)[1] if "-->" in text else text
    start = body.index("### Principle IV")
    end = body.index("### Principle V", start)
    # Wrapping is a formatting choice and must not decide whether a check passes: the phrases
    # asserted below straddle line breaks in the file as written.
    return re.sub(r"\s+", " ", body[start:end])


def test_the_constitution_names_three_exceptions_and_bounds_the_static_key_rule() -> None:
    """Both sentences, asserted together — because they had to move together (ADR-0058).

    Amending the exception count while leaving *"static API keys are prohibited without
    exception"* standing would reproduce, inside one principle, exactly the contradiction this
    amendment exists to end. So the row fails if either half regresses.

    **The count moved again in 038** (ADR-0062, constitution v1.6.0): the version-control App key
    behind the authoring credential path is the third. This row is what makes the enumeration a
    boundary rather than a habit — it fails on every change to the count, so each one is a
    deliberate amendment with a motivating record rather than a number somebody edited.
    """
    principle = _principle_iv()

    assert "exactly three named exceptions" in principle
    for superseded in ("exactly one named exception", "exactly two named exceptions"):
        assert superseded not in principle, (
            f"Principle IV still reads {superseded!r}; the enumeration has grown and the clause "
            f"must say so, because a closed list that grows by interpretation is not a closed list"
        )
    assert "prohibited as workload credentials" in principle
    assert "prohibited without exception" not in principle, (
        "the static-key sentence still reads as an absolute while the exception clause above it "
        "names two — the two sentences must agree or the principle contradicts itself"
    )
    # The bounds are what make the softened rule a rule rather than a hole.
    for bound in ("trust store", "per task", "never persisted"):
        assert bound in principle, f"the exception is unbounded: {bound!r} is missing"


def test_the_amendment_cites_the_record_that_motivated_it() -> None:
    """Principle X: an amendment carries its motivating ADR, or nobody can find the argument.

    Every exception names one, so the clause is a set of decisions rather than a list of
    allowances — and each can be argued with by whoever reads it next.
    """
    principle = _principle_iv()
    for adr, filename in (
        ("ADR-0044", "docs/adr/0044-authz-doctrine-and-credential-translation.md"),
        ("ADR-0058", "docs/adr/0058-model-credential-brokering.md"),
        ("ADR-0062", "docs/adr/0062-authoring-credentials-are-vended-per-task.md"),
    ):
        assert adr in principle, f"the exception clause names no motivating record for {adr}"
        assert (ROOT / filename).is_file()


def test_no_jobspec_hands_a_vendor_key_to_a_workload() -> None:
    """SC-007's config half — the leak a grep *can* see.

    A jobspec `env` block is the shortest path to a working model call and the exact thing the
    amended sentence forbids: a key in a jobspec is a standing credential, readable by anything in
    the allocation and by anyone who can read the job. The brokered path exists so nobody needs to.

    This does not assert the runtime property; see the module docstring.
    """
    offenders: list[str] = []
    for spec in sorted(JOBS.rglob("*.hcl")):
        text = spec.read_text()
        for name in VENDOR_KEY_NAMES:
            if re.search(rf"\b{name}\b", text):
                offenders.append(f"{spec.relative_to(ROOT)}: {name}")

    assert offenders == [], (
        f"a jobspec passes a vendor credential to a workload: {offenders}. The credential is "
        f"read from the trust store per task under the workload's own attested identity — an "
        f"environment variable is the standing credential Principle IV forbids"
    )


def test_the_check_has_jobspecs_to_check() -> None:
    """Without this, moving or renaming the jobs directory makes the row above vacuous."""
    assert len(list(JOBS.rglob("*.hcl"))) >= 3
