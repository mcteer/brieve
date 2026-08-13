# SPDX-License-Identifier: Apache-2.0
"""Normalize a pasted forge URL into the ownership / clone identifier (047)."""

from __future__ import annotations

import re

from core.authoring.request import RequestRefused

_GITHUB_HTTPS = re.compile(
    r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)
_GITHUB_SSH = re.compile(r"^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$", re.IGNORECASE)
_OWNER_REPO = re.compile(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")


def normalize_repository_url(raw: str) -> str:
    """Return ``owner/repo`` or refuse.

    Ownership and acquisition compare this exact form. HTTPS, SSH, and bare ``owner/repo``
    are accepted for GitHub; other hosts refuse rather than guess.
    """
    text = (raw or "").strip()
    if not text:
        raise RequestRefused(
            "a repository URL is required",
            reason_code="repository_required",
        )
    for pattern in (_GITHUB_HTTPS, _GITHUB_SSH, _OWNER_REPO):
        match = pattern.match(text)
        if match:
            owner, repo = match.group(1), match.group(2)
            if repo.endswith(".git"):
                repo = repo[: -len(".git")]
            return f"{owner}/{repo}"
    raise RequestRefused(
        "repository URL is not a recognized GitHub repository",
        reason_code="repository_unrecognized",
    )


__all__ = ["normalize_repository_url"]
