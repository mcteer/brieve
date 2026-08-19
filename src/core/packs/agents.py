# SPDX-License-Identifier: Apache-2.0
"""Load a pack's pinned phase instruction. Product-blind: pack name in, bytes out."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.authoring.progress import PhaseName
from core.packs.loader import PackLoader, content_digest
from core.packs.manifest import ManifestError

_CANDIDATES_MARKER = "prompt-tune/candidates"


@dataclass(frozen=True)
class PhaseAgents:
    """Resolved, verified bytes ready to steer one phase."""

    pack: str
    phase: PhaseName
    version: str
    digest: str
    body: str
    provenance_path: str


def load_phase_agents(
    pack_name: str,
    phase: PhaseName | str,
    *,
    loader: PackLoader,
    packs_root: Path,
) -> PhaseAgents:
    """Return the pinned ``AGENTS.md`` for ``pack_name`` × ``phase``.

    Never reads repository-root ``AGENTS.md``, never reads ``SKILL.md`` or ``pack.toml``
    prose as the body, never reads ``evals/prompt-tune/candidates/``.
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
    return PhaseAgents(
        pack=pack_name,
        phase=named,
        version=pin.version,
        digest=pin.digest,
        body=body,
        provenance_path=str(provenance),
    )


__all__ = ["PhaseAgents", "load_phase_agents"]
