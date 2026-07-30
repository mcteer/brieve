# SPDX-License-Identifier: Apache-2.0
"""Pack loading, and the six refusals it earns.

Every refusal here exists because its *natural* symptom accuses the wrong component. A
non-repeatable tool with no observer does not fail at load by default — it fails when a run
is interrupted, resolves to CANNOT_DETERMINE, and parks, arbitrarily far from the manifest
that caused it. A pack with no probe does not fail at load — it fails when every one of its
tools is denied `dependency_unavailable` naming a product that is running fine.

So each of these rows is really asserting the same property: **the failure lands where the
mistake was made.**
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.hooks.types import CapabilityKind, HookContext, HookDecision, HookPhase
from core.packs.loader import (
    FilesystemPackLoader,
    InMemoryPackLoader,
    parse_manifest,
    validate_manifest,
)
from core.packs.manifest import (
    ManifestError,
    PackHookDeclaration,
    PackManifest,
    ToolDeclaration,
)
from core.packs.registration import PlatformBindings, load_packs, register_pack
from core.registry.memory import ToolRegistry


def _tool(name: str = "read", **overrides: object) -> ToolDeclaration:
    fields: dict[str, object] = {
        "name": name,
        "risk_class": "read",
        "transport": "native",
        "handler": "h",
    }
    fields.update(overrides)
    return ToolDeclaration(**fields)  # type: ignore[arg-type]


def _manifest(name: str = "vault", **overrides: object) -> PackManifest:
    fields: dict[str, object] = {
        "name": name,
        "product": name,
        "version": "0.1.0",
        "provenance": "authored",
        "probe": f"{name}_probe",
        "tools": (_tool(product=name, product_mode="federate", product_action=f"{name}.read"),),
    }
    fields.update(overrides)
    return PackManifest(**fields)  # type: ignore[arg-type]


def _allow(ctx: HookContext) -> HookDecision:
    return HookDecision(outcome="allow", reason_code="ok")


def _bindings(*products: str) -> PlatformBindings:
    return PlatformBindings(
        handlers={"h": lambda args: "ok"},
        observers={"obs": object()},  # type: ignore[dict-item]
        hooks={"hk": _allow},
        probes={f"{p}_probe": (lambda product: (True, "up")) for p in products},
    )


# --- The manifest parses, and the whole of it or none of it -----------------------------


def test_a_manifest_parses_into_records() -> None:
    manifest = parse_manifest(
        {
            "pack": {
                "name": "vault",
                "product": "vault",
                "version": "0.1.0",
                "provenance": "authored",
                "probe": "vault_probe",
            },
            "tools": [
                {
                    "name": "read",
                    "risk_class": "secret_touching",
                    "transport": "native",
                    "handler": "vault_read",
                    "product": "vault",
                    "product_mode": "federate",
                    "product_action": "vault.read",
                }
            ],
        }
    )
    assert manifest.name == "vault"
    assert manifest.tools[0].risk_class == "secret_touching"


def test_an_adopted_pack_must_declare_upstream() -> None:
    """`adopted` without a pinned commit is a supply chain with nothing to check.

    ADR-0004's whole mechanism is provenance against a real upstream. A pack claiming
    adoption with no repository and no commit claims the review happened without leaving
    anything for the review to have been about.
    """
    with pytest.raises(ManifestError) as caught:
        parse_manifest(
            {
                "pack": {
                    "name": "terraform",
                    "product": "terraform",
                    "version": "0.1.0",
                    "provenance": "adopted",
                }
            }
        )
    assert caught.value.reason_code == "malformed_manifest"


def test_a_malformed_manifest_refuses_the_whole_load() -> None:
    """Not a partial load.

    Holding some of a pack is worse than holding none: the tools that parsed would be
    callable while the hooks that did not would be absent, so enforcement would be missing
    with nothing reporting it missing.
    """
    registry = ToolRegistry()
    loader = InMemoryPackLoader()
    loader.add(_manifest("vault"))
    with pytest.raises(ManifestError):
        load_packs(
            ["vault", "absent"], loader=loader, registry=registry, bindings=_bindings("vault")
        )


# --- The six refusals -------------------------------------------------------------------


def test_a_pack_may_not_register_a_governance_hook() -> None:
    """Enforcement is the platform's.

    `has_required_governance_hooks` identifies the built-ins by
    `capability_kind == GOVERNANCE`. A pack able to register at that kind could satisfy the
    platform's own enforcement-is-whole check *with its own hook* — enforcement authored by
    whoever ships a pack, which is what Principle III exists to prevent.
    """
    with pytest.raises(ManifestError) as caught:
        validate_manifest(
            _manifest(
                hooks=(
                    PackHookDeclaration(
                        name="mine",
                        phase=HookPhase.PRE,
                        capability_kind=CapabilityKind.GOVERNANCE,
                        handler="hk",
                    ),
                )
            )
        )
    assert caught.value.reason_code == "governance_hook_from_pack"


def test_a_non_repeatable_tool_needs_an_observer() -> None:
    """Otherwise an interrupted step resolves to CANNOT_DETERMINE and parks the run.

    Every `write` and `destructive` pack tool is non-repeatable, so without this every
    interesting pack tool would ship with 005's re-observation unreachable — and the
    symptom would be a run that never finishes, nowhere near the manifest.
    """
    with pytest.raises(ManifestError) as caught:
        validate_manifest(_manifest(tools=(_tool("apply", risk_class="write", repeatable=False),)))
    assert caught.value.reason_code == "observer_required"


def test_a_non_repeatable_tool_with_an_observer_is_fine() -> None:
    validate_manifest(
        _manifest(tools=(_tool("apply", risk_class="write", repeatable=False, observer="obs"),))
    )


def test_a_product_mode_binding_needs_its_product() -> None:
    """In the pack's vocabulary, not as a bare ValueError from the registry."""
    with pytest.raises(ManifestError) as caught:
        validate_manifest(_manifest(tools=(_tool("read", product_mode="federate"),)))
    assert caught.value.reason_code == "incomplete_product_binding"


def test_a_pack_reaching_a_product_must_name_a_probe() -> None:
    """The sharpest trap in this feature.

    `HealthChecker.products()` derives its subject set from the registry, so a loaded pack's
    product is monitored the moment it registers — and the default `unconfigured_probe`
    returns unreachable. That records UNHEALTHY, and the dependency gate then denies every
    call to this pack's tools with `dependency_unavailable`, **naming a product that is
    running fine**.
    """
    with pytest.raises(ManifestError) as caught:
        validate_manifest(_manifest(probe=None))
    assert caught.value.reason_code == "probe_required"


def test_a_pack_reaching_no_product_needs_no_probe() -> None:
    """The bound is on reaching a product, not on being a pack."""
    validate_manifest(_manifest(probe=None, tools=(_tool("think"),)))


def test_a_pack_below_the_eval_floor_refuses_at_load() -> None:
    """Refused, not warned about.

    A floor nothing enforces is a suggestion, and a suite of one happy path greens a gate
    while asserting nothing. Refusing at load puts the failure where the pack is added
    rather than where a gate later reports a number nobody reads.
    """
    with pytest.raises(ManifestError) as caught:
        validate_manifest(_manifest(eval_suites=("must_deny",), eval_case_counts={"must_deny": 2}))
    assert caught.value.reason_code == "insufficient_eval_coverage"


def test_a_digest_mismatch_refuses_and_names_the_file(tmp_path: Path) -> None:
    """What makes "pinned" checkable rather than asserted.

    A skill whose bytes changed without its pin changing is exactly the ungated drift
    Principle VIII exists to stop, and it is invisible without a hash.
    """
    pack_dir = tmp_path / "vault"
    (pack_dir / "skills").mkdir(parents=True)
    skill = pack_dir / "skills" / "read.md"
    skill.write_text("the real content")
    wrong = hashlib.sha256(b"what the manifest claims").hexdigest()
    (pack_dir / "pack.toml").write_text(
        f"""
[pack]
name = "vault"
product = "vault"
version = "0.1.0"
provenance = "authored"
probe = "vault_probe"

[[skills]]
name = "read"
path = "skills/read.md"
version = "1"
digest = "{wrong}"
"""
    )
    with pytest.raises(ManifestError) as caught:
        FilesystemPackLoader(tmp_path).load("vault")
    assert caught.value.reason_code == "digest_mismatch"
    assert "skills/read.md" in str(caught.value)


def test_a_correct_digest_loads(tmp_path: Path) -> None:
    pack_dir = tmp_path / "vault"
    (pack_dir / "skills").mkdir(parents=True)
    body = b"the real content"
    (pack_dir / "skills" / "read.md").write_bytes(body)
    (pack_dir / "pack.toml").write_text(
        f"""
[pack]
name = "vault"
product = "vault"
version = "0.1.0"
provenance = "authored"
probe = "vault_probe"

[[skills]]
name = "read"
path = "skills/read.md"
version = "1"
digest = "{hashlib.sha256(body).hexdigest()}"
"""
    )
    assert FilesystemPackLoader(tmp_path).load("vault").skills[0].name == "read"


# --- Loading executes nothing, and two packs coexist ------------------------------------


def test_a_manifest_may_only_name_what_the_platform_provides() -> None:
    """The structural half of "loading executes nothing from the pack".

    A manifest naming a handler the platform does not have refuses. It cannot supply one —
    there is no field for a callable — so there is no arrangement of pack content that runs
    code.
    """
    registry = ToolRegistry()
    with pytest.raises(ManifestError) as caught:
        register_pack(
            _manifest(tools=(_tool("read", handler="something_the_pack_wrote"),)),
            registry=registry,
            bindings=_bindings("vault"),
        )
    assert caught.value.reason_code == "unresolved_binding"


def test_two_packs_load_side_by_side_with_risk_classes_intact() -> None:
    registry = ToolRegistry()
    loader = InMemoryPackLoader()
    loader.add(_manifest("vault", tools=(_tool("read", risk_class="secret_touching"),)))
    loader.add(_manifest("terraform", tools=(_tool("plan", risk_class="read"),)))

    loaded = load_packs(
        ["vault", "terraform"],
        loader=loader,
        registry=registry,
        bindings=_bindings("vault", "terraform"),
    )

    assert set(loaded) == {"vault", "terraform"}
    assert registry.resolve("read").risk_class == "secret_touching"
    assert registry.resolve("plan").risk_class == "read"
