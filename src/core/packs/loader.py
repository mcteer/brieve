# SPDX-License-Identifier: Apache-2.0
"""Loading a pack: parse the manifest, verify every digest, refuse in the pack's vocabulary.

**Verification happens at load, not at review.** Review is when somebody looked; load is
when it matters, and the two are separated by however long it takes for the person who
looked to stop being the person deploying.

**A refusal names the pack's own concept.** A pack whose non-repeatable tool has no
observer refuses `observer_required`, not `CANNOT_DETERMINE` three phases later when a run
parks. A pack declaring a product with no probe refuses `probe_required`, not
`dependency_unavailable` naming a product that is running fine. Each of these is a real
failure mode this feature would otherwise have shipped, and in every case the natural
symptom points at the wrong artifact.

**Nothing here executes pack content.** The manifest is parsed as data; handlers, observers,
and probes are names resolved later against what the platform provides.
"""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path
from typing import Any, Protocol

from core.authoring.progress import PHASE_ORDER, PhaseName
from core.hooks.types import CapabilityKind, HookPhase
from core.packs.manifest import (
    AgentPin,
    ManifestError,
    PackHookDeclaration,
    PackManifest,
    SkillPin,
    ToolDeclaration,
    ToolPathGrant,
    UnsatisfiableRecommendation,
    UpstreamPin,
    WorkflowDeclaration,
)

#: Minimum eval cases a pack must ship per suite it declares, and how many of those must be
#: cases the agent is required to refuse or decline.
#:
#: **A pack below the floor is refused at load, not warned about.** A floor nothing enforces
#: is a suggestion, and a suite of one happy path greens a gate while asserting nothing —
#: content is where that is easiest to let slide. Refusing at load puts the failure where
#: the pack is added rather than where a gate later reports a number nobody reads.
MINIMUM_CASES_PER_SUITE = 5


class PackLoader(Protocol):
    """Where packs come from.

    A protocol so a hermetic row does not need a directory. Two packs loading side by side
    and neither leaking is a property about isolation, not about the filesystem, and it
    should be assertable without one.
    """

    def load(self, name: str) -> PackManifest:
        """Return the manifest, verified. Raise ManifestError with a reason code."""
        ...

    def available(self) -> list[str]:
        """Pack names this loader can produce."""
        ...


def _require(condition: bool, message: str, *, reason_code: str) -> None:
    if not condition:
        raise ManifestError(message, reason_code=reason_code)


def parse_manifest(data: dict[str, Any]) -> PackManifest:
    """Parse a manifest document into records, refusing anything malformed.

    A malformed manifest refuses the **whole** load. Partial loading would leave the
    platform holding some of a pack, which is worse than holding none of it: the tools that
    parsed would be callable while the hooks that did not would be absent, and enforcement
    would be missing without anything reporting it missing.
    """
    try:
        pack = data["pack"]
        name = str(pack["name"])
        product = str(pack["product"])
        version = str(pack["version"])
        provenance = str(pack["provenance"])
    except (KeyError, TypeError) as exc:
        raise ManifestError(
            f"manifest missing required field: {exc}", reason_code="malformed_manifest"
        ) from exc

    _require(
        provenance in ("adopted", "authored"),
        f"unknown provenance: {provenance}",
        reason_code="malformed_manifest",
    )

    upstream = None
    if provenance == "adopted":
        raw = data.get("upstream")
        _require(
            isinstance(raw, dict),
            "adopted packs must declare [upstream] — the pinned commit is what makes "
            "provenance checkable rather than asserted (ADR-0004)",
            reason_code="malformed_manifest",
        )
        assert isinstance(raw, dict)
        try:
            upstream = UpstreamPin(
                repository=str(raw["repository"]),
                commit=str(raw["commit"]),
                licence=str(raw["licence"]),
                retrieved=str(raw["retrieved"]),
            )
        except KeyError as exc:
            raise ManifestError(
                f"[upstream] missing required field: {exc}", reason_code="malformed_manifest"
            ) from exc

    tools = tuple(_parse_tool(entry) for entry in data.get("tools", []))
    skills = tuple(_parse_skill(entry) for entry in data.get("skills", []))
    agents = tuple(_parse_agent(entry) for entry in data.get("agents", []))
    hooks = tuple(_parse_hook(entry) for entry in data.get("hooks", []))
    workflows = tuple(_parse_workflow(entry) for entry in data.get("workflows", []))

    evals = data.get("evals", {}) or {}
    suites = tuple(str(s) for s in evals.get("suites", []))
    counts = {str(k): int(v) for k, v in (evals.get("cases", {}) or {}).items()}

    manifest = PackManifest(
        name=name,
        product=product,
        version=version,
        provenance="adopted" if provenance == "adopted" else "authored",
        probe=str(pack["probe"]) if pack.get("probe") else None,
        upstream=upstream,
        tools=tools,
        skills=skills,
        agents=agents,
        hooks=hooks,
        workflows=workflows,
        eval_suites=suites,
        eval_case_counts=counts,
    )
    validate_manifest(manifest)
    return manifest


def _parse_tool(entry: dict[str, Any]) -> ToolDeclaration:
    try:
        return ToolDeclaration(
            name=str(entry["name"]),
            risk_class=entry["risk_class"],
            transport=entry["transport"],
            handler=str(entry["handler"]),
            observer=str(entry["observer"]) if entry.get("observer") else None,
            product_mode=entry.get("product_mode", "none"),
            product=str(entry["product"]) if entry.get("product") else None,
            product_action=str(entry["product_action"]) if entry.get("product_action") else None,
            repeatable=bool(entry.get("repeatable", True)),
            paths=_parse_tool_paths(entry),
        )
    except KeyError as exc:
        raise ManifestError(
            f"tool declaration missing required field: {exc}", reason_code="malformed_manifest"
        ) from exc


def _parse_tool_paths(entry: dict[str, Any]) -> tuple[ToolPathGrant, ...]:
    """What this tool reaches, declared so a reviewer does not have to read the handler.

    **A `secret_touching` tool MUST declare this.** The same shape as the rule that a
    non-repeatable tool must declare an observer, and for the same reason: a pack that
    withholds the fact governance turns on is one whose review is guesswork. This is the
    cheapest moment to require it — the author is right there, and the alternative is a
    reviewer inferring reach from code months later.

    Enforced at load rather than used at runtime. Authority is the ceiling's, per allocation
    and short-lived (ADR-0057); this is documentation the platform refuses to ship without.
    """
    declared = entry.get("paths") or []
    if not declared and entry.get("risk_class") == "secret_touching":
        raise ManifestError(
            f"tool {entry.get('name')!r} is secret_touching and declares no `paths`. A tool "
            f"whose reach is only discoverable by reading its handler makes its own review "
            f"guesswork, and this is the cheapest moment to say it. Declare `paths`, or "
            f"lower `risk_class` if it does not touch secrets after all.",
            reason_code="malformed_manifest",
        )
    grants: list[ToolPathGrant] = []
    for item in declared:
        try:
            caps = tuple(str(c) for c in item["capabilities"])
            grants.append(ToolPathGrant(path=str(item["path"]), capabilities=caps))
        except (KeyError, TypeError) as exc:
            raise ManifestError(
                f"tool {entry.get('name')!r} has a malformed `paths` entry: {exc}. Each needs "
                f"`path` and `capabilities`.",
                reason_code="malformed_manifest",
            ) from exc
    return tuple(grants)


def _parse_unsatisfiable(entry: dict[str, Any], *, skill: str) -> UnsatisfiableRecommendation:
    """One declared step no registry tool can carry out.

    Both fields are required and neither may be blank. An empty `recommendation` would render
    an empty bullet into a pull request — a reviewer seeing a heading with nothing under it
    learns less than one seeing no heading at all.
    """
    try:
        capability = str(entry["capability"]).strip()
        recommendation = str(entry["recommendation"]).strip()
    except KeyError as exc:
        raise ManifestError(
            f"skill {skill!r} unsatisfiable entry missing required field: {exc}",
            reason_code="malformed_manifest",
        ) from exc
    _require(
        bool(capability) and bool(recommendation),
        f"skill {skill!r} declares an unsatisfiable recommendation with an empty "
        f"capability or recommendation; an empty one renders a bullet a reviewer "
        f"cannot act on",
        reason_code="malformed_manifest",
    )
    return UnsatisfiableRecommendation(capability=capability, recommendation=recommendation)


def _parse_skill(entry: dict[str, Any]) -> SkillPin:
    """Parse one `[[skills]]` entry, preserving declared order in every sequence.

    `tomllib` keeps array-of-table order, and both sequences stay tuples, so delivery order
    and pull-request bullet order are the manifest's own order rather than whatever a dict
    or set iteration produced that day (FR-006, FR-018).
    """
    try:
        name = str(entry["name"])
        return SkillPin(
            name=name,
            path=str(entry["path"]),
            version=str(entry["version"]),
            digest=str(entry["digest"]),
            phases=tuple(str(phase) for phase in entry.get("phases", [])),
            unsatisfiable=tuple(
                _parse_unsatisfiable(item, skill=name) for item in entry.get("unsatisfiable", [])
            ),
            unsatisfiable_reviewed_at=str(entry.get("unsatisfiable_reviewed_at", "")).strip(),
        )
    except KeyError as exc:
        raise ManifestError(
            f"skill pin missing required field: {exc}", reason_code="malformed_manifest"
        ) from exc


def _parse_agent(entry: dict[str, Any]) -> AgentPin:
    try:
        phase = str(entry["phase"])
        path = str(entry["path"])
        version = str(entry["version"])
        digest = str(entry["digest"])
    except KeyError as exc:
        raise ManifestError(
            f"agent pin missing required field: {exc}", reason_code="malformed_manifest"
        ) from exc
    try:
        named = PhaseName(phase)
    except ValueError as exc:
        raise ManifestError(
            f"agent pin names unknown phase {phase!r}", reason_code="unknown_phase"
        ) from exc
    canonical = f"agents/{named.value}/AGENTS.md"
    if ".." in path.split("/") or path != canonical:
        raise ManifestError(
            f"agent pin path {path!r} must be {canonical}",
            reason_code="malformed_manifest",
        )
    if not version.strip():
        raise ManifestError("agent pin version must be non-empty", reason_code="malformed_manifest")
    return AgentPin(phase=named.value, path=path, version=version, digest=digest)


def _parse_hook(entry: dict[str, Any]) -> PackHookDeclaration:
    try:
        return PackHookDeclaration(
            name=str(entry["name"]),
            phase=HookPhase(entry["phase"]),
            capability_kind=CapabilityKind(entry.get("capability_kind", "other")),
            handler=str(entry["handler"]),
        )
    except (KeyError, ValueError) as exc:
        raise ManifestError(
            f"hook declaration invalid: {exc}", reason_code="malformed_manifest"
        ) from exc


def _parse_workflow(entry: dict[str, Any]) -> WorkflowDeclaration:
    try:
        return WorkflowDeclaration(
            name=str(entry["name"]),
            minimum_tier=int(entry["minimum_tier"]),
            paved=bool(entry.get("paved", False)),
        )
    except (KeyError, ValueError) as exc:
        raise ManifestError(
            f"workflow declaration invalid: {exc}", reason_code="malformed_manifest"
        ) from exc


def validate_manifest(manifest: PackManifest) -> None:
    """Every refusal a manifest can earn, in the pack's own vocabulary.

    Each of these is a real failure this feature would otherwise ship, and each one's
    natural symptom accuses the wrong component.
    """
    for hook in manifest.hooks:
        # Enforcement is the platform's. A pack registering at GOVERNANCE could satisfy
        # `has_required_governance_hooks` with its own hook — the enforcement-is-whole
        # check passing because a third party supplied the enforcement it checks for.
        _require(
            hook.capability_kind is not CapabilityKind.GOVERNANCE,
            f"pack hook {hook.name!r} declares capability_kind=governance; enforcement is "
            f"the platform's and a pack may not register at that kind",
            reason_code="governance_hook_from_pack",
        )

    for tool in manifest.tools:
        # Without an observer an interrupted non-repeatable step resolves to
        # CANNOT_DETERMINE and PARKS THE RUN. The symptom is a run that will not finish,
        # arbitrarily far from the manifest that caused it.
        _require(
            tool.repeatable or tool.observer is not None,
            f"tool {tool.name!r} is non-repeatable and declares no observer; an interrupted "
            f"step would resolve to CANNOT_DETERMINE and park the run",
            reason_code="observer_required",
        )
        # Otherwise `ToolRegistry.register` raises a bare ValueError from three layers down.
        _require(
            tool.product_mode == "none" or bool(tool.product and tool.product_action),
            f"tool {tool.name!r} sets product_mode={tool.product_mode!r} without product "
            f"and product_action",
            reason_code="incomplete_product_binding",
        )

    # The sharpest trap in this feature. `HealthChecker.products()` derives its subject set
    # from the registry, so a loaded pack's product is monitored the moment it registers —
    # but the probe is SUPPLIED, and the default `unconfigured_probe` returns unreachable.
    # That records UNHEALTHY, and `dependency_pre_hook` then denies every call to this
    # pack's tools with `dependency_unavailable`, naming a product that is running fine.
    _require(
        not manifest.declares_a_product or bool(manifest.probe),
        f"pack {manifest.name!r} declares tools reaching {manifest.product!r} but names no "
        f"probe; without one the product records UNHEALTHY and every one of its tools is "
        f"denied while the product is up",
        reason_code="probe_required",
    )

    for suite in manifest.eval_suites:
        shipped = manifest.eval_case_counts.get(suite, 0)
        _require(
            shipped >= MINIMUM_CASES_PER_SUITE,
            f"pack {manifest.name!r} ships {shipped} cases for suite {suite!r}, below the "
            f"floor of {MINIMUM_CASES_PER_SUITE}",
            reason_code="insufficient_eval_coverage",
        )

    _validate_skill_bindings(manifest)

    seen_phases: set[str] = set()
    for pin in manifest.agents:
        _require(
            pin.phase not in seen_phases,
            f"pack {manifest.name!r} declares duplicate phase {pin.phase!r}",
            reason_code="duplicate_phase",
        )
        seen_phases.add(pin.phase)

    if any("author" in workflow.name for workflow in manifest.workflows):
        required = {phase.value for phase in PHASE_ORDER}
        _require(
            seen_phases == required,
            f"pack {manifest.name!r} declares an authoring workflow but [[agents]] does not "
            f"cover every phase",
            reason_code="agents_incomplete",
        )


def _validate_skill_bindings(manifest: PackManifest) -> None:
    """Every refusal a skill binding can earn (051, FR-007, FR-019).

    Each is separate because SC-005 requires a distinct reason per failure and none reported
    as another. A binding that refuses for the wrong reason sends whoever reads the refusal to
    the wrong line of the manifest.
    """
    known_phases = {phase.value for phase in PHASE_ORDER}
    backed = {pin.phase for pin in manifest.agents}
    seen: set[str] = set()

    for skill in manifest.skills:
        _require(
            skill.name not in seen,
            f"pack {manifest.name!r} declares two skills named {skill.name!r}; a binding, a "
            f"pin and a delivered digest would each be ambiguous",
            reason_code="duplicate_skill",
        )
        seen.add(skill.name)

        for phase in skill.phases:
            _require(
                phase in known_phases,
                f"pack {manifest.name!r} binds skill {skill.name!r} to {phase!r}, which is not "
                f"a Build phase. The phases are {sorted(known_phases)}",
                reason_code="unknown_phase",
            )
            # A binding to a phase the pack ships no instruction for could never be
            # delivered: `load_phase_agents` refuses `agents_missing` before assembly, so the
            # binding would sit in the manifest reading like configuration while doing
            # nothing. Refused here, where the manifest is in front of somebody.
            _require(
                phase in backed,
                f"pack {manifest.name!r} binds skill {skill.name!r} to phase {phase!r}, for "
                f"which it declares no [[agents]] instruction; the binding could never be "
                f"delivered",
                reason_code="skill_binding_unbacked",
            )

        # THE DECLARATION MUST KEEP PACE WITH THE BYTES (FR-019). A bump changes `digest`;
        # if nobody re-read the content, this field still records the old one and the
        # mismatch says so. Required even of a skill declaring nothing: "nothing here is
        # unsatisfiable" goes stale exactly like a non-empty claim, and the pull request
        # would then tell a reviewer that less work remains than actually does.
        _require(
            skill.unsatisfiable_reviewed_at == skill.digest,
            f"pack {manifest.name!r} skill {skill.name!r}: unsatisfiable_reviewed_at is "
            f"{skill.unsatisfiable_reviewed_at or '(unset)'!r} but the skill pins "
            f"{skill.digest!r}. The declaration was examined against different bytes than the "
            f"ones this pack ships, so what the platform cannot do may be understated",
            reason_code="unsatisfiable_declaration_unreviewed",
        )


def content_digest(data: bytes) -> str:
    """SHA-256 over content bytes, matching the audit chain's hashing."""
    return hashlib.sha256(data).hexdigest()


class FilesystemPackLoader:
    """Packs from `packs/<name>/pack.toml`, with every content digest verified."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def available(self) -> list[str]:
        if not self._root.is_dir():
            return []
        return sorted(p.name for p in self._root.iterdir() if (p / "pack.toml").is_file())

    def load(self, name: str) -> PackManifest:
        pack_dir = self._root / name
        manifest_path = pack_dir / "pack.toml"
        if not manifest_path.is_file():
            raise ManifestError(f"no manifest at {manifest_path}", reason_code="pack_not_loaded")
        with manifest_path.open("rb") as handle:
            document = tomllib.load(handle)
        manifest = parse_manifest(document)
        self._verify_digests(manifest, pack_dir)
        return manifest

    def _verify_digests(self, manifest: PackManifest, pack_dir: Path) -> None:
        """Every skill's bytes must hash to what the manifest recorded.

        This is what makes "pinned" (ADR-0030) checkable rather than asserted. A skill whose
        content changed without its pin changing is the ungated drift Principle VIII exists
        to stop, and it is invisible without a hash.
        """
        for skill in manifest.skills:
            path = pack_dir / skill.path
            if not path.is_file():
                raise ManifestError(
                    f"skill {skill.name!r} declares {skill.path} which is not present",
                    reason_code="digest_mismatch",
                )
            actual = content_digest(path.read_bytes())
            if actual != skill.digest:
                raise ManifestError(
                    f"skill {skill.name!r} at {skill.path}: manifest records {skill.digest}, "
                    f"content hashes to {actual}",
                    reason_code="digest_mismatch",
                )

        for pin in manifest.agents:
            path = pack_dir / pin.path
            if not path.is_file():
                raise ManifestError(
                    f"phase {pin.phase!r} declares {pin.path} which is not present",
                    reason_code="agents_missing",
                )
            raw = path.read_bytes()
            if not raw.decode("utf-8", errors="replace").strip():
                raise ManifestError(
                    f"phase {pin.phase!r} AGENTS.md is empty",
                    reason_code="agents_empty",
                )
            actual = content_digest(raw)
            if actual != pin.digest:
                raise ManifestError(
                    f"phase {pin.phase!r} at {pin.path}: manifest records {pin.digest}, "
                    f"content hashes to {actual}",
                    reason_code="digest_mismatch",
                )
            provenance = pack_dir / "agents" / pin.phase / "PROVENANCE.md"
            if not provenance.is_file() or not provenance.read_text(encoding="utf-8").strip():
                raise ManifestError(
                    f"phase {pin.phase!r} is missing a non-empty PROVENANCE.md sibling",
                    reason_code="agents_provenance_missing",
                )


class InMemoryPackLoader:
    """Manifests handed in directly, for rows that need a pack and not a directory."""

    def __init__(self, manifests: dict[str, PackManifest] | None = None) -> None:
        self._manifests = dict(manifests or {})

    def add(self, manifest: PackManifest) -> None:
        validate_manifest(manifest)
        self._manifests[manifest.name] = manifest

    def available(self) -> list[str]:
        return sorted(self._manifests)

    def load(self, name: str) -> PackManifest:
        manifest = self._manifests.get(name)
        if manifest is None:
            raise ManifestError(f"pack not loaded: {name}", reason_code="pack_not_loaded")
        return manifest


__all__ = [
    "MINIMUM_CASES_PER_SUITE",
    "FilesystemPackLoader",
    "InMemoryPackLoader",
    "PackLoader",
    "content_digest",
    "parse_manifest",
    "validate_manifest",
]
