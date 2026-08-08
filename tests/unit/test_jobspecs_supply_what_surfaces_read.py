# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a surface is given what it needs by the job that runs it.

Configuration and tooling, and both arrived here the same way: something the code needs, that
the job never supplied, failing quietly enough to survive a full green suite.

**`HARNESS_DEFAULT_TENANT` was set in `.env` from the beginning and reached no jobspec.** Every
served surface read an empty string, and the omission survived because it was invisible twice
over: `resolve_tenant` is normally reached *with* a subject claim, so the environment fallback
almost never fires; and all three surfaces were empty in the same way, so they agreed.

**Accidental agreement is the dangerous kind.** Set it on one surface and not another and the
drift probe queries for an adopted version under `tenant-local`, finds none, and reports
permanent drift on every endorsed source — while the console writes content under `""`. Nothing
errors. Nothing looks wrong. The two surfaces simply file records in different places.

**The tooling half was found by writing the gate too narrowly.** 045's endorsed sync needs
`git`; the API ran a `-slim` Python image without it, and the row written to catch that named
`api.nomad.hcl` — a jobspec, not a property. The drift probe on the *mcp* service reaches a
customer's repository too, and its image was missed for exactly as long as it took to run the
supervisory loop and read the output. A rule that names a file passes while the defect lives
one file over.

The pairing is derived from the jobspecs themselves rather than listed here, so a new surface
is covered by existing, and a surface that stops needing something stops being asked for it.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
JOBS = ROOT / "infra" / "jobs"

#: Variables whose absence a surface must not paper over. Deliberately NOT "every variable a
#: module mentions": plenty are legitimately optional and carry a default that means something
#: — `MCP_INTERVAL_SECONDS` has a cadence, `OIDC_WORKLOAD_ISSUER` absent is the fail-closed
#: posture. These are the ones where an unset value silently changes where data goes.
REQUIRED_OF_SURFACES = ("HARNESS_DEFAULT_TENANT",)


def _module_of(jobspec: pathlib.Path) -> str:
    """Which surface a jobspec runs, read from its own command."""
    found = re.search(r"surfaces\.[a-z_.]+", jobspec.read_text())
    return found.group(0) if found else ""


def _source_for(module: str) -> str:
    path = ROOT / "src" / (module.replace(".", "/") + ".py")
    return path.read_text() if path.exists() else ""


def _pairs() -> list[tuple[pathlib.Path, str, str]]:
    """(jobspec, module, source) for every job that runs a surface."""
    pairs = []
    for jobspec in sorted(JOBS.glob("*.hcl")):
        module = _module_of(jobspec)
        source = _source_for(module)
        if module and source:
            pairs.append((jobspec, module, source))
    return pairs


def test_the_pairing_finds_something() -> None:
    """The control. A scan that matched no jobspecs would pass this file forever.

    This repository has shipped three checks that passed by measuring nothing, and each of
    them now carries a row like this one.
    """
    pairs = _pairs()

    assert len(pairs) >= 4, f"only {len(pairs)} jobspec/module pairs found; the scan is not working"
    assert any("api" in job.name for job, _, _ in pairs)
    assert any("mcp" in job.name for job, _, _ in pairs)


def test_every_surface_that_reads_a_required_variable_is_given_it() -> None:
    """The row. Reading configuration nobody supplies is reading a default nobody chose."""
    missing = []
    for jobspec, module, source in _pairs():
        spec = jobspec.read_text()
        for variable in REQUIRED_OF_SURFACES:
            reads = variable in source or "resolve_tenant" in source
            if reads and variable not in spec:
                missing.append(f"{jobspec.name} runs {module}, which needs {variable}")

    assert not missing, (
        f"{missing}. A surface reading configuration the job never supplies gets a default "
        f"nobody chose — and where that default decides WHERE records are filed, two surfaces "
        f"disagreeing about it is silent: nothing errors, and they simply write to different "
        f"places."
    )


def test_no_surface_reads_the_tenant_around_its_own_resolver() -> None:
    """`resolve_tenant` refuses when nothing is configured. Reading the variable directly
    with an empty default is the accident it exists to prevent, and 045 introduced three.

    *"A default tenant chosen by accident is still a tenant, and silently writing records
    under an invented value would put them somewhere nobody would think to look for them."*
    An empty string is such a value.
    """
    offenders = []
    for path in (ROOT / "src" / "surfaces").rglob("*.py"):
        source = path.read_text()
        if 'os.environ.get("HARNESS_DEFAULT_TENANT"' in source:
            offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, (
        f"{offenders} read the tenant from the environment directly. `resolve_tenant()` is "
        f"the one place that decides what an unset tenant means, and it refuses — which is "
        f"the posture its own module docstring argues for."
    )


#: Where the platform reaches a customer's repository. A module importing this needs `git` in
#: whatever image runs it — derived rather than listed, because the first version of this rule
#: named a jobspec and the second surface that needed it was missed.
EGRESS_MODULE = "core.endorsed_sync"


def test_every_job_running_a_surface_that_clones_declares_an_image_that_can() -> None:
    """A `-slim` Python image carries no `git`, and the sync shells out to it.

    Without this the console renders perfectly and every sync fails at the click, while the
    drift probe reports UNKNOWN on every endorsed source — both of which read as the
    customer's repository being wrong when the transport is missing at our end.

    Narrow on purpose: only the surfaces that actually clone. A rule saying every image needs
    git would be false of the ones that never reach outward, and would push people to widen
    images for no reason. **The authoring tier is deliberately out of scope** — it verifies
    `git` and `gh` in its own command and exits `tooling_missing` at task start, which is the
    louder posture and the right one for a tier that can do nothing else without them.
    """
    offenders = []
    for jobspec, module, source in _pairs():
        if EGRESS_MODULE not in source:
            continue
        images = re.findall(r'image\s*=\s*"([^"]+)"', jobspec.read_text())
        if any(image.endswith("-slim") for image in images):
            offenders.append(f"{jobspec.name} runs {module}, which clones, on {images}")

    assert not offenders, (
        f"{offenders}. A `-slim` Python image has no `git`, so the surface renders its pages "
        f"and fails every sync — a failure that reads as the customer's repository being "
        f"wrong when the transport is missing at ours."
    )


def test_at_least_one_surface_is_known_to_clone() -> None:
    """The control. If the import moved or was renamed this row would pass over an empty set,
    and the rule above would assert nothing about anything."""
    cloning = [module for _, module, source in _pairs() if EGRESS_MODULE in source]

    assert cloning, (
        f"no surface imports {EGRESS_MODULE}, so the image rule matches nothing. Either the "
        f"module moved, or the endorsed sync is no longer reachable from a served surface."
    )


def test_the_variable_is_declared_where_it_is_used() -> None:
    """An HCL `var.` reference with no `variable` block does not plan, so this would be caught
    by `terraform`—except these are Nomad jobspecs, which `terraform validate` never sees.

    Worth its own row precisely because the tool that would normally catch it is not in this
    lane.
    """
    for jobspec in sorted(JOBS.glob("*.hcl")):
        spec = jobspec.read_text()
        for reference in set(re.findall(r"var\.([a-z_]+)", spec)):
            assert f'variable "{reference}"' in spec, (
                f"{jobspec.name} references var.{reference} and declares no such variable; "
                f"Nomad fails this at submit, and no lane here would have said so first"
            )
