# SPDX-License-Identifier: Apache-2.0
"""Promotion: the only way content or a model version enters the platform.

**All three checks, or it does not promote.** ADR-0004 names provenance, an injection-lens
review, and a passing eval run. Two of three is a supply chain with a hole, and the hole is
whichever one somebody was in a hurry about.

The three are deliberately *independent*. Provenance says the bytes are the ones upstream
published; the lens says the content is not trying to redirect the agent; the evals say
behaviour did not regress. A skill can pass any two and fail the third — an authentic,
benign skill that breaks a suite; an authentic skill carrying an injection; a clean skill
whose provenance cannot be verified. Each of those is a different problem and each blocks.

**`promote_model_version` is here too**, and it is the positive case behind the negative one
`test_no_auto_tracking` asserts. That row says auto-tracking does not *exist*; this is the
path a deliberate bump actually takes. A feature that only forbade the automatic route
without building the manual one would make the forbidden route the only one that worked.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from core.evals.injection_patterns import INJECTION_PATTERNS
from core.packs.loader import content_digest


class PromotionRefused(Exception):
    """A promotion that did not clear every gate. Names which one, and why."""

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class InjectionFinding:
    """One pattern that fired, with what it was trying to do."""

    pattern_name: str
    explanation: str
    excerpt: str


@dataclass(frozen=True)
class LensResult:
    """What the lens saw. Recorded whether or not it refused.

    A clean result is evidence the review happened; without one, "the lens passed" and "the
    lens never ran" look identical afterwards.
    """

    clean: bool
    findings: tuple[InjectionFinding, ...] = ()

    @property
    def summary(self) -> str:
        if self.clean:
            return "no injection-shaped content found"
        return "; ".join(f"{f.pattern_name}: {f.explanation}" for f in self.findings)


def injection_lens(content: str) -> LensResult:
    """Scan content for instruction-shaped text targeting the agent.

    Returns rather than raises, because the caller needs the *result* either way: a clean
    scan is recorded as evidence, and only `promote_skill` decides that a finding blocks.
    Raising here would make a clean scan indistinguishable from no scan.
    """
    findings = [
        InjectionFinding(
            pattern_name=pattern.name,
            explanation=pattern.explanation,
            excerpt=match.group(0)[:120],
        )
        for pattern in INJECTION_PATTERNS
        if (match := pattern.pattern.search(content))
    ]
    return LensResult(clean=not findings, findings=tuple(findings))


@dataclass(frozen=True)
class PromotionEvidence:
    """What was checked, recorded as a record rather than asserted as a claim.

    Every field is something somebody can go and re-derive. "Provenance verified" with no
    digest is a sentence; a digest is a thing that can be checked again next year.
    """

    skill_name: str
    from_version: str
    to_version: str
    upstream_commit: str
    content_digest: str
    lens: LensResult
    suites_passed: tuple[str, ...] = ()
    fields: dict[str, str] = field(default_factory=dict)


def promote_skill(
    *,
    skill_name: str,
    content: bytes,
    from_version: str,
    to_version: str,
    upstream_commit: str,
    expected_digest: str,
    suites_passed: tuple[str, ...],
    required_suites: tuple[str, ...],
) -> PromotionEvidence:
    """Promote a skill bump, or refuse naming the check that blocked it.

    Order is deliberate: **provenance first**. Running an injection lens over content whose
    origin has not been established scans an arbitrary blob and reports it clean, which is
    worse than not scanning — it produces evidence about the wrong bytes.
    """
    if not upstream_commit.strip():
        raise PromotionRefused(
            f"skill {skill_name!r} declares no upstream commit; a bump with no provenance "
            f"cannot be checked against what upstream published",
            reason_code="promotion_incomplete",
        )

    actual = content_digest(content)
    if actual != expected_digest:
        raise PromotionRefused(
            f"skill {skill_name!r}: content hashes to {actual}, the record says "
            f"{expected_digest}. The bytes are not the ones whose provenance was recorded",
            reason_code="digest_mismatch",
        )

    lens = injection_lens(content.decode("utf-8", errors="replace"))
    if not lens.clean:
        raise PromotionRefused(
            f"skill {skill_name!r} contains content that targets the agent — {lens.summary}",
            reason_code="injection_suspected",
        )

    missing = tuple(s for s in required_suites if s not in suites_passed)
    if missing:
        raise PromotionRefused(
            f"skill {skill_name!r} has not passed {list(missing)}; passing is not the same "
            f"as unchanged, and a suite that did not run has said nothing either way",
            reason_code="promotion_incomplete",
        )

    return PromotionEvidence(
        skill_name=skill_name,
        from_version=from_version,
        to_version=to_version,
        upstream_commit=upstream_commit,
        content_digest=actual,
        lens=lens,
        suites_passed=suites_passed,
    )


def promote_model_version(
    *,
    pack: str,
    model: str,
    role: str,
    suites_passed: tuple[str, ...],
    required_suites: tuple[str, ...],
    qualified_by: str,
    judge: str,
    scorer: str = "",
) -> dict[str, str]:
    """Qualify a new (pack × model × role) cell, or refuse.

    A model bump **is a new cell needing qualification** — not an edit to an existing one.
    Treating it as an edit is how a version bump inherits a qualification it never earned,
    which is auto-tracking with a manual step in front of it.

    **What qualified this** — a `judge` or a `scorer`, and refused when both are absent
    (ADR-0063). `judge` names a model that scored the cell; `scorer` names a mechanical
    comparison against a human-authored reference. Empty for both is permitted only for the
    seed-qualified first judge, which is the single case where nothing sits above it.

    The second shape exists because 038's `write` qualification has **no judge at all**: both
    correctness gates check an artefact against a reference's declared property set, and all
    three must-deny classes are mechanical. A cell whose qualification is *stronger* than a
    judged one — the regress terminates one link earlier, at the human who wrote the reference,
    with no scoring model to qualify — would otherwise have been refused for not being judged.

    Naming some judge that did no scoring, to satisfy a string check, is the move 027 refused:
    *a gate that passes by vocabulary is worse than no gate.*
    """
    missing = tuple(s for s in required_suites if s not in suites_passed)
    if missing:
        raise PromotionRefused(
            f"cell {pack}:{model}:{role} has not passed {list(missing)}",
            reason_code="promotion_incomplete",
        )
    if qualified_by not in ("fixture", "live"):
        raise PromotionRefused(
            f"cell {pack}:{model}:{role} must record whether it was qualified against a "
            f"recording or a live model; got {qualified_by!r}",
            reason_code="promotion_incomplete",
        )
    if not judge.strip() and not scorer.strip() and role != "judge":
        raise PromotionRefused(
            f"cell {pack}:{model}:{role} names neither a judge nor a scorer; only the "
            f"seed-qualified first judge has nothing above it",
            reason_code="promotion_incomplete",
        )
    # A MODEL DOES NOT JUDGE ITS OWN OUTPUT (ADR-0067).
    #
    # ADR-0052 constrains how a judge earns its place and says nothing about which model may
    # judge which output — so every live cell this platform had promoted was qualified by the
    # model it qualifies. The failure mode is correlated blindness rather than dishonesty: a
    # judge sharing the generator's misconceptions is least equipped to see exactly the errors
    # the generator systematically makes, and the resulting high score is evidence of nothing.
    #
    # 032 paid for the near miss — the same scorer served subject and judge, the judge
    # inherited the agent's protocol, and qualification moved from >90% to 55%. That was
    # visible because a NUMBER moved. Judgement bleed moves no number: a cell agreeing with
    # itself looks exactly like a cell that is right.
    if judge.strip() and judge.strip() == model.strip():
        raise PromotionRefused(
            f"cell {pack}:{model}:{role} names itself as its own judge. A model does not "
            f"judge its own output (ADR-0067) — a judge that shares the generator's blind "
            f"spots measures fluency, not correctness",
            reason_code="self_judged_cell",
        )
    return {
        "pack": pack,
        "model": model,
        "role": role,
        "qualified_by": qualified_by,
        "judge": judge,
        "scorer": scorer,
    }


def promote_phase_agents(
    *,
    pack: str,
    files: dict[str, bytes],
    provenance: dict[str, str],
    expected_digests: dict[str, str],
    versions: dict[str, str],
    suites_passed: tuple[str, ...],
    packs_root: Path,
    refinement_available: bool,
) -> dict[str, str]:
    """Copy a whole five-file instruction set into ``packs/``, or copy none of it.

    Authored files do not invent ``upstream_commit``. Provenance is the sibling file.
    """
    from core.authoring.progress import PHASE_ORDER
    from core.evals.suites import BUILD_AGENTS_QUALIFICATION, PHASE_AGENTS_QUALIFICATION

    if not refinement_available:
        raise PromotionRefused(
            f"pack {pack!r} cannot promote phase agents without the prompt-tune extra",
            reason_code="refinement_unavailable",
        )
    required = {phase.value for phase in PHASE_ORDER}
    if set(files) != required:
        raise PromotionRefused(
            f"pack {pack!r} must supply all five phase files or none",
            reason_code="promotion_incomplete",
        )
    missing = tuple(
        name
        for name in (PHASE_AGENTS_QUALIFICATION, BUILD_AGENTS_QUALIFICATION)
        if name not in suites_passed
    )
    if missing:
        raise PromotionRefused(
            f"pack {pack!r} has not passed {list(missing)}",
            reason_code="promotion_incomplete",
        )
    pack_dir = Path(packs_root) / pack
    for phase in PHASE_ORDER:
        name = phase.value
        body = files[name]
        actual = content_digest(body)
        expected = expected_digests.get(name, "")
        if actual != expected:
            raise PromotionRefused(
                f"pack {pack!r} phase {name}: bytes are not the recorded digest",
                reason_code="digest_mismatch",
            )
        note = provenance.get(name, "").strip()
        if not note:
            raise PromotionRefused(
                f"pack {pack!r} phase {name} has no provenance sibling",
                reason_code="agents_provenance_missing",
            )
        lens = injection_lens(body.decode("utf-8", errors="replace"))
        if not lens.clean:
            raise PromotionRefused(
                f"pack {pack!r} phase {name} contains injection-shaped content — {lens.summary}",
                reason_code="injection_suspected",
            )
    # Whole-set copy only after every check. Partial writes are forbidden.
    recorded: dict[str, str] = {}
    for phase in PHASE_ORDER:
        name = phase.value
        dest_dir = pack_dir / "agents" / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / "AGENTS.md").write_bytes(files[name])
        (dest_dir / "PROVENANCE.md").write_text(provenance[name], encoding="utf-8")
        recorded[name] = expected_digests[name]
        recorded[f"{name}.version"] = versions.get(name, "0.1.0")
    manifest_path = pack_dir / "pack.toml"
    if manifest_path.is_file():
        text = manifest_path.read_text(encoding="utf-8")
        for phase in PHASE_ORDER:
            name = phase.value
            digest = expected_digests[name]
            version = versions.get(name, "0.1.0")
            text = _rewrite_agent_pin(text, phase=name, digest=digest, version=version)
        manifest_path.write_text(text, encoding="utf-8")
    return recorded


def _rewrite_agent_pin(text: str, *, phase: str, digest: str, version: str) -> str:
    """Update the [[agents]] digest/version for one phase. Whole-file, not a parser."""
    marker = re.search(
        rf'path\s*=\s*"agents/{re.escape(phase)}/AGENTS\.md"',
        text,
    )
    if marker is None:
        return text
    start = marker.start()
    block_start = text.rfind("[[agents]]", 0, start)
    nxt = text.find("[[agents]]", start)
    block_end = nxt if nxt >= 0 else len(text)
    if block_start < 0:
        return text
    block = text[block_start:block_end]
    block = _replace_field(block, "version", version)
    block = _replace_field(block, "digest", digest)
    return text[:block_start] + block + text[block_end:]


def _replace_field(block: str, field: str, value: str) -> str:
    lines = []
    for line in block.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(f"{field}"):
            indent = line[: len(line) - len(stripped)]
            eol = "\n" if line.endswith("\n") else ""
            lines.append(f'{indent}{field} = "{value}"{eol}')
        else:
            lines.append(line)
    return "".join(lines)


__all__ = [
    "InjectionFinding",
    "LensResult",
    "PromotionEvidence",
    "PromotionRefused",
    "injection_lens",
    "promote_model_version",
    "promote_phase_agents",
    "promote_skill",
]
