# SPDX-License-Identifier: Apache-2.0
"""Repository URL normalization (047)."""

from __future__ import annotations

import pytest

from core.authoring.repository_id import (
    extract_propose_from_message,
    normalize_repository_url,
)
from core.authoring.request import RequestRefused


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://github.com/mcteer/brieve-demo", "mcteer/brieve-demo"),
        ("https://github.com/mcteer/brieve-demo.git", "mcteer/brieve-demo"),
        ("git@github.com:mcteer/brieve-demo.git", "mcteer/brieve-demo"),
        ("mcteer/brieve-demo", "mcteer/brieve-demo"),
    ],
)
def test_normalize_github_forms(raw: str, expected: str) -> None:
    assert normalize_repository_url(raw) == expected


def test_refuse_empty_and_unknown() -> None:
    with pytest.raises(RequestRefused) as empty:
        normalize_repository_url("  ")
    assert empty.value.reason_code == "repository_required"
    with pytest.raises(RequestRefused) as bad:
        normalize_repository_url("https://gitlab.com/acme/app")
    assert bad.value.reason_code == "repository_unrecognized"


def test_extract_propose_from_chat_bubble() -> None:
    repo, task = extract_propose_from_message(
        "I need you to create a terraform template that will provision "
        "the appropriate infrastructure in AWS for this application: "
        "https://github.com/mcteer/brieve-demo"
    )
    assert repo == "https://github.com/mcteer/brieve-demo"
    assert "terraform" in task.lower()
    assert "https://" not in task


def test_extract_propose_requires_url_and_task() -> None:
    with pytest.raises(RequestRefused) as no_url:
        extract_propose_from_message("add terraform please")
    assert no_url.value.reason_code == "repository_required"
    with pytest.raises(RequestRefused) as no_task:
        extract_propose_from_message("https://github.com/mcteer/brieve-demo")
    assert no_task.value.reason_code == "task_required"
