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

from core.hooks.types import CapabilityKind, HookPhase
from core.packs.manifest import (
    ManifestError,
    PackHookDeclaration,
    PackManifest,
    SkillPin,
    ToolDeclaration,
    ToolPathGrant,
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


def _parse_skill(entry: dict[str, Any]) -> SkillPin:
    try:
        return SkillPin(
            name=str(entry["name"]),
            path=str(entry["path"]),
            version=str(entry["version"]),
            digest=str(entry["digest"]),
        )
    except KeyError as exc:
        raise ManifestError(
            f"skill pin missing required field: {exc}", reason_code="malformed_manifest"
        ) from exc


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
