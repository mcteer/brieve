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

#: A GitHub URL embedded in a free-text Propose message (chat bubble).
_GITHUB_IN_TEXT = re.compile(
    r"https?://(?:www\.)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?",
    re.IGNORECASE,
)


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


def extract_propose_from_message(message: str) -> tuple[str, str]:
    """Split a chat message into ``(repository_url, task)`` for Propose intake.

    The person pastes one bubble that names the repo and the ask. The platform finds the
    first GitHub URL; the rest of the text is the task. No agent picker, no second field.
    """
    text = (message or "").strip()
    if not text:
        raise RequestRefused("a message is required", reason_code="task_required")
    match = _GITHUB_IN_TEXT.search(text)
    if match is None:
        raise RequestRefused(
            "include a GitHub repository URL in your message",
            reason_code="repository_required",
        )
    repo_raw = match.group(0)
    task = (text[: match.start()] + text[match.end() :]).strip()
    task = re.sub(r"\s+", " ", task).strip(" :,-")
    if not task:
        raise RequestRefused(
            "say what should change, not only which repository",
            reason_code="task_required",
        )
    return repo_raw, task


__all__ = ["extract_propose_from_message", "normalize_repository_url"]
