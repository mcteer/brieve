# SPDX-License-Identifier: Apache-2.0
"""Load a pack's pinned phase instruction. Product-blind: pack name in, bytes out."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from core.authoring.progress import PhaseName
from core.packs.loader import PackLoader, content_digest
from core.packs.manifest import ManifestError, PackManifest

_CANDIDATES_MARKER = "prompt-tune/candidates"

#: Ceiling on the assembled instruction — instruction plus every skill bound to the phase.
#:
#: **Refuse, never truncate.** A truncated instruction delivers partial practice while the
#: record claims the whole skill, which is worse than delivering none: the run looks governed
#: and is not. FR-009 also requires the stop to be deterministic and recorded, and the only
#: other candidate signal — the model provider rejecting an over-long prompt — is none of
#: those things. It arrives after the call is paid for, it differs per provider and per
#: model (so two qualified cells would disagree about whether the same pack loads), and the
#: eval lane never sees it, so no row could assert it. A byte count over digest-pinned content
#: is the same number on every run, in every profile, on every model.
#:
#: 256 KiB against a largest current assembly of 16,603 bytes (Write plus both HashiCorp
#: skills) — roughly 15× headroom, so no legitimate adoption trips it, and far below any
#: qualified cell's context window, so a refusal means somebody bound something structurally
#: wrong: a vendored directory, a corpus. Fixed with its reasoning for the same purpose as
#: `READ_BUDGET_BYTES` — an unfixed threshold is one that gets raised until the corpus passes.
INSTRUCTION_BUDGET_BYTES = 256 * 1024


#: Fixed delimiters around each delivered skill. They are the ONLY bytes the platform
#: contributes to the instruction — adopted content is never edited, filtered, reordered
#: internally, or truncated (ADR-0004, FR-015) — and they are what makes "the skill's content
#: is present in the instruction" assertable rather than approximate.
SKILL_OPEN = "--- BEGIN PINNED SKILL: {name} ({digest}) ---"
SKILL_CLOSE = "--- END PINNED SKILL: {name} ---"


@dataclass(frozen=True)
class DeliveredSkill:
    """One skill that went into a phase's instruction, and the bytes it actually was.

    ``digest`` is re-verified against the file read at delivery, never copied from the
    manifest: a value copied from the pin would agree with the pin by construction and could
    not disagree with the content, which is the only thing it is for.
    """

    name: str
    digest: str


@dataclass(frozen=True)
class PhaseAgents:
    """Resolved, verified bytes ready to steer one phase."""

    pack: str
    phase: PhaseName
    version: str
    #: The ``[[agents]]`` pin's digest — of ``AGENTS.md`` alone. A pin identity, deliberately
    #: NOT a hash of the assembly: the pin shape is unchanged by 051, and what the assembly
    #: was composed of is recorded by ``skills``, each member carrying its own digest.
    digest: str
    #: THE ASSEMBLED INSTRUCTION — the instruction file, then every skill bound to this
    #: phase. This is what the model receives, and the only field a caller may send to one.
    body: str
    provenance_path: str
    #: What went into ``body``, in delivery order. Empty when nothing is bound, in which case
    #: ``body`` is byte-identical to the instruction file (FR-011).
    skills: tuple[DeliveredSkill, ...] = ()


def unsatisfiable_recommendations(manifest: PackManifest) -> tuple[str, ...]:
    """What this pack's bound skills recommend that no registry tool can carry out.

    **From the manifest, and from nothing else** (FR-018). Not the progress record, not a
    model's account of its own work — a declaration is pinned, reviewed, and identical on
    every run, which is what makes the sentence a reviewer reads the same in two pull
    requests over entirely different content.

    **Every skill bound to any phase**, rather than to the phases that happened to run. The
    two sets are the same at the only moment this is asked: a run that opens a pull request
    has necessarily executed all five phases, because `open_proposal` follows the Propose
    bind, which follows Judge permitting publication, which follows Write, Plan and Research.
    Reading the manifest rather than the progress record is what makes run-independence
    structural instead of carefully maintained.

    Order is `[[skills]]` declaration order, then declaration order within a skill.
    """
    out: list[str] = []
    for skill in manifest.skills:
        if not skill.phases:
            continue
        out.extend(item.recommendation for item in skill.unsatisfiable)
    return tuple(out)


def assemble_instruction(
    agents_body: str,
    skills: tuple[DeliveredSkill, ...],
    bodies: Mapping[str, str],
) -> str:
    """The instruction file, then every bound skill. What a phase's model receives.

    **Pure, and it takes the instruction bytes as a parameter.** It never re-derives them
    from a pin, and that is the whole design of this function rather than an incidental
    property. `load_phase_agents` calls it with the pinned, digest-verified `AGENTS.md`; the
    eval scorers call it with whatever bytes a corpus case references — including a candidate
    that has no pin at all, which is exactly what re-qualification needs.

    Routing the scorers through `load_phase_agents` instead would deadlock: editing a phase
    file makes its `[[agents]]` digest stale, the loader refuses `digest_mismatch`, the
    suites cannot score, and `promote_phase_agents` requires the suites to have passed. A
    candidate has no pin by definition, and scoring one must not require having promoted it.

    One implementation, two callers. A second implementation would let a suite pass on bytes
    production never sends.

    **Nothing is bound → the instruction, unchanged.** No delimiter, no trailing byte, so a
    phase that binds no skill is byte-identical to what it was before 051 (FR-011).
    """
    if not skills:
        return agents_body
    parts = [agents_body]
    for skill in skills:
        parts.append(
            "\n".join(
                (
                    "",
                    SKILL_OPEN.format(name=skill.name, digest=skill.digest),
                    bodies[skill.name],
                    SKILL_CLOSE.format(name=skill.name),
                )
            )
        )
    return "\n".join(parts)


def _read_bound_skills(
    manifest: PackManifest,
    *,
    pack_name: str,
    phase: PhaseName,
    pack_dir: Path,
) -> tuple[tuple[DeliveredSkill, ...], dict[str, str]]:
    """Read and verify every skill bound to ``phase``, in manifest declaration order.

    **Verified here, at delivery** — not merely at load (FR-003). Load-time verification says
    the bytes were right when the pack was loaded; a phase is entitled to know they are right
    when a model is about to be steered by them.

    **Order is `[[skills]]` declaration order.** It is the only ordering the manifest already
    carries, so identical manifest content produces an identical instruction (FR-006). Sorting
    by name would be equally deterministic and would silently reorder on a rename.

    There is no fallback. A skill that is missing, empty, or drifted stops the phase; neither
    delivering unverified content nor proceeding without the skill is an option (FR-004).
    """
    delivered: list[DeliveredSkill] = []
    bodies: dict[str, str] = {}
    for pin in manifest.skills:
        if phase.value not in pin.phases:
            continue
        path = (pack_dir / pin.path).resolve()
        try:
            path.relative_to(pack_dir.resolve())
        except ValueError as exc:
            raise ManifestError(
                f"pack {pack_name!r} skill {pin.name!r} path escapes the pack directory",
                reason_code="skill_missing",
            ) from exc
        if not path.is_file():
            raise ManifestError(
                f"pack {pack_name!r} phase {phase.value!r} is bound to skill {pin.name!r}, "
                f"whose file {pin.path} is not present",
                reason_code="skill_missing",
            )
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ManifestError(
                f"pack {pack_name!r} skill {pin.name!r} could not be read",
                reason_code="skill_missing",
            ) from exc
        body = raw.decode("utf-8")
        if not body.strip():
            raise ManifestError(
                f"pack {pack_name!r} skill {pin.name!r} is empty; an empty skill delivers no "
                f"practice while the record claims a governed one",
                reason_code="skill_empty",
            )
        actual = content_digest(raw)
        if actual != pin.digest:
            raise ManifestError(
                f"pack {pack_name!r} skill {pin.name!r}: bytes hash to {actual}, the pin "
                f"records {pin.digest}. No model is asked to author under unverified practice",
                reason_code="digest_mismatch",
            )
        delivered.append(DeliveredSkill(name=pin.name, digest=actual))
        bodies[pin.name] = body
    return tuple(delivered), bodies


def load_phase_agents(
    pack_name: str,
    phase: PhaseName | str,
    *,
    loader: PackLoader,
    packs_root: Path,
) -> PhaseAgents:
    """Return the assembled instruction for ``pack_name`` × ``phase``.

    ``PhaseAgents.body`` is the pinned ``AGENTS.md`` **plus every skill bound to this phase**
    (051, FR-001). Before that, a pack could pin a skill, name it as practice in its phase
    prose, and deliver it to nobody — which is what `content_pins` recorded as governance.

    Never reads repository-root ``AGENTS.md``, never reads ``pack.toml`` prose as the body,
    never reads ``evals/prompt-tune/candidates/``. A ``SKILL.md`` is still not a valid
    ``[[agents]]`` pin: a skill reaches a phase by being **bound**, and only ever alongside
    the instruction, never in place of it.
    """
    try:
        named = phase if isinstance(phase, PhaseName) else PhaseName(str(phase))
    except ValueError as exc:
        raise ManifestError(f"unknown phase {phase!r}", reason_code="unknown_phase") from exc
    manifest = loader.load(pack_name)
    pin = next((item for item in manifest.agents if item.phase == named.value), None)
    if pin is None:
        raise ManifestError(
            f"pack {pack_name!r} has no [[agents]] pin for phase {named.value!r}",
            reason_code="agents_missing",
        )
    posix = pin.path.replace("\\", "/")
    if _CANDIDATES_MARKER in posix or posix.endswith("SKILL.md") or posix == "AGENTS.md":
        raise ManifestError(
            f"pack {pack_name!r} phase {named.value!r} pin is not an executed agents file",
            reason_code="agents_missing",
        )
    pack_dir = Path(packs_root) / pack_name
    path = (pack_dir / pin.path).resolve()
    try:
        path.relative_to(pack_dir.resolve())
    except ValueError as exc:
        raise ManifestError(
            f"pack {pack_name!r} phase {named.value!r} path escapes the pack directory",
            reason_code="agents_missing",
        ) from exc
    if not path.is_file():
        raise ManifestError(
            f"pack {pack_name!r} phase {named.value!r} file is not present",
            reason_code="agents_missing",
        )
    raw = path.read_bytes()
    body = raw.decode("utf-8")
    if not body.strip():
        raise ManifestError(
            f"pack {pack_name!r} phase {named.value!r} AGENTS.md is empty",
            reason_code="agents_empty",
        )
    actual = content_digest(raw)
    if actual != pin.digest:
        raise ManifestError(
            f"pack {pack_name!r} phase {named.value!r}: pin digest does not match bytes",
            reason_code="digest_mismatch",
        )
    provenance = pack_dir / "agents" / named.value / "PROVENANCE.md"
    if not provenance.is_file() or not provenance.read_text(encoding="utf-8").strip():
        raise ManifestError(
            f"pack {pack_name!r} phase {named.value!r} is missing PROVENANCE.md",
            reason_code="agents_provenance_missing",
        )
    delivered, bodies = _read_bound_skills(
        manifest, pack_name=pack_name, phase=named, pack_dir=pack_dir
    )
    assembled = assemble_instruction(body, delivered, bodies)
    # AFTER assembly, BEFORE return — so no partial instruction can leave this function.
    # Truncating would deliver part of a skill while the record names the whole one, which
    # reads as governed and is not (FR-009).
    size = len(assembled.encode("utf-8"))
    if size > INSTRUCTION_BUDGET_BYTES:
        raise ManifestError(
            f"pack {pack_name!r} phase {named.value!r}: the assembled instruction is "
            f"{size} bytes, over the {INSTRUCTION_BUDGET_BYTES}-byte budget. Delivering part "
            f"of it would steer the model with practice the record claims in full",
            reason_code="instruction_too_large",
        )
    return PhaseAgents(
        pack=pack_name,
        phase=named,
        version=pin.version,
        digest=pin.digest,
        body=assembled,
        provenance_path=str(provenance),
        skills=delivered,
    )


__all__ = [
    "INSTRUCTION_BUDGET_BYTES",
    "DeliveredSkill",
    "PhaseAgents",
    "assemble_instruction",
    "load_phase_agents",
    "unsatisfiable_recommendations",
]
