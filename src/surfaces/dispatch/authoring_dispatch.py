# SPDX-License-Identifier: Apache-2.0
"""Preparing an authoring dispatch: validate, acquire, then hand the tier a subject (041, T013).

**Acquisition happens here, and "here" is the point.** FR-027 forbids the clone inside the
hardened tier: the analysing task holds no attested identity and no egress, and getting the
subject is not permitted to become the exception that gives it either. This module runs in the
dispatching context — the same context that already validates the request — so the credential
that clones never enters the allocation.

The order is the requirement. `AuthoringRequest.validate()` first, because a refusal that
arrives once a checkout exists leaves something on disk to leak; then acquisition; then
`resolve_subject_mount` against the **produced** path, so the platform-tree refusal 038 wrote
still governs an input 038 never produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.authoring.acquisition import AcquiredSubject, acquire_subject, release_subject
from core.authoring.request import AuthoringRequest
from core.isolation.tier import SubjectMount


@dataclass(frozen=True)
class PreparedAuthoringRun:
    """Everything a dispatch needs, and nothing the tier must not receive."""

    request: AuthoringRequest
    subject: AcquiredSubject
    mount: SubjectMount

    @property
    def meta(self) -> dict[str, str]:
        """The dispatch metadata. **No credential**, on ADR-0048's rule."""
        return {
            "subject_path": self.mount.source,
            "target_repository": self.request.target_repository,
            "base_commit": self.subject.commit,
        }


def prepare_authoring_run(
    request: AuthoringRequest,
    *,
    run_tenant_id: str,
    owned_repositories: frozenset[str],
    packs_declaring_authoring: frozenset[str],
    into: Path,
    platform_tree: Path,
    token: str | None = None,
    runner: Any = None,
) -> PreparedAuthoringRun:
    """Validate, clone, and bound — or refuse before anything exists.

    Raises:
        RequestRefused: any of the request's own refusals, or acquisition's
            (`subject_unreachable`, `revision_missing`, `acquisition_refused`), or the
            platform-tree refusal against the produced path.
    """
    request.validate(
        run_tenant_id=run_tenant_id,
        owned_repositories=owned_repositories,
        packs_declaring_authoring=packs_declaring_authoring,
    )

    subject = acquire_subject(
        target_repository=request.target_repository,
        into=into,
        token=token,
        runner=runner,
    )

    from core.authoring.request import resolve_subject_mount

    try:
        mount = resolve_subject_mount(str(subject.path), platform_tree=platform_tree)
    except Exception:
        # A produced path that fails the platform-tree check is a bug in acquisition, not a
        # bad request — and it must not leave a checkout behind while it is diagnosed.
        release_subject(subject)
        raise

    return PreparedAuthoringRun(request=request, subject=subject, mount=mount)


__all__ = ["PreparedAuthoringRun", "prepare_authoring_run"]
