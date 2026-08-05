# SPDX-License-Identifier: Apache-2.0
"""What a person asked for, and where it may land (038, FR-007; research R31, R33).

**A dispatch payload, not a northbound operation.** An authoring request reaches the platform
as the payload of an ordinary dispatched run whose definition carries `author_file` — so
Principle II's surface parity is *inherited rather than owed*, and a row asserts no new verb
was added. An absent parity row and a deliberately-inherited one look identical in a diff, and
only one of them is a gate regression.

**Three refusals live here, and each one is the last line of its own defence:**

* *ownership* — a version-control App installation is scoped to the installing account or
  organisation, **not to an individual**, so two requesters inside one organisation share one
  installation and the credential would reach either's repositories. The credential bounds the
  installation; **this check alone bounds the requester**.
* *the declared workflow* — ADR-0038 had three independent gates on who may author for what:
  the ceiling, the pack's declared workflow, and the tier. With `open_proposal` a platform tool
  (ADR-0064), the pack no longer gates publishing at all, so this is one of one.
* *the subject path* — the subject differs every run, so its mount source is per-dispatch while
  `repo_mounted` is a declared boolean. A dispatch naming the platform's own tree would satisfy
  every clause of the hardened posture while mounting exactly what the tier exists to keep out.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.errors import CoreError
from core.isolation.tier import SubjectMount


class RequestRefused(CoreError):
    """An authoring request that will not be started. Carries the reason code."""

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass(frozen=True)
class AuthoringRequest:
    """One ask: author this, into a repository of mine."""

    correlation_id: str
    #: Required, never defaulted. `AuditEntry` demands one, and it is the field the hash chain
    #: keeps *inside* itself precisely because it decides who may read the record — so a
    #: request that did not carry one would write entries under a tenancy nobody chose.
    tenant_id: str
    requester: str
    target_repository: str
    task: str
    pack: str

    def validate(
        self,
        *,
        run_tenant_id: str,
        owned_repositories: frozenset[str],
        packs_declaring_authoring: frozenset[str],
    ) -> None:
        """Refuse before anything is produced, or return.

        **Before**, not after: a refusal that arrives once files exist leaves something on disk
        to leak, and "refused after producing" and "refused before producing" are different
        postures wearing one word.
        """
        if not self.tenant_id.strip():
            raise RequestRefused(
                "an authoring request carries no tenant; the trail's bounding dimension is not "
                "something to infer",
                reason_code="tenant_required",
            )
        if self.tenant_id != run_tenant_id:
            raise RequestRefused(
                f"request tenant {self.tenant_id!r} is not the run's {run_tenant_id!r}; a "
                f"request scoped to one tenant writing entries under another corrupts the one "
                f"field the hash chain keeps inside itself",
                reason_code="tenant_mismatch",
            )
        if self.pack not in packs_declaring_authoring:
            raise RequestRefused(
                f"pack {self.pack!r} declares no authoring workflow; a pack that has not said "
                f"it supports authoring has not been reviewed for it",
                reason_code="pack_declares_no_authoring",
            )
        if self.target_repository not in owned_repositories:
            raise RequestRefused(
                f"{self.target_repository!r} is not a repository {self.requester!r} owns. The "
                f"publishing credential is installation-scoped, not requester-scoped, so this "
                f"check is the only thing bounding the requester",
                reason_code="repository_not_owned",
            )


def resolve_subject_mount(source: str, *, platform_tree: Path) -> SubjectMount:
    """The subject mount, or refuse `subject_is_platform_tree` (research R25).

    The tier's `repo_mounted` clause is a **declared boolean** and the mount source is
    **per-dispatch**, so nothing else stands between a dispatch naming the platform's own tree
    and a hardened posture that reports itself clean. This turns the row into a check of a
    *path* rather than of a claim about one.

    Read-only always: a writable subject fails `is_hardened()` anyway, and constructing one here
    would only move the refusal later.
    """
    if not source.strip():
        raise RequestRefused(
            "an authoring request names no subject to analyse",
            reason_code="subject_required",
        )
    resolved = Path(source).resolve()
    platform = platform_tree.resolve()
    if resolved == platform or platform in resolved.parents or resolved in platform.parents:
        raise RequestRefused(
            f"the subject at {source!r} resolves inside the platform's own tree at {platform}; "
            f"mounting it read-only would satisfy every clause of the hardened posture while "
            f"handing a redirected analyser exactly what the tier exists to keep out",
            reason_code="subject_is_platform_tree",
        )
    return SubjectMount(source=str(resolved), read_only=True)


__all__ = ["AuthoringRequest", "RequestRefused", "resolve_subject_mount"]
