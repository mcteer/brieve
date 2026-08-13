# SPDX-License-Identifier: Apache-2.0
"""046 S4 — portal renders primary_answer first; legacy claims[] still replay."""

from __future__ import annotations

from typing import Any

from fastapi.templating import Jinja2Templates

from surfaces.portal.app import TEMPLATES, answer_markup, answer_segments
from surfaces.portal.highlight import highlight_code
from surfaces.portal.relay import ApiResponse

_TEMPLATES = Jinja2Templates(directory=str(TEMPLATES))
_TEMPLATES.env.filters["answer_segments"] = answer_segments
_TEMPLATES.env.filters["answer_markup"] = answer_markup
_TEMPLATES.env.filters["highlight_code"] = highlight_code


def _render(payload: dict[str, Any]) -> str:
    return _TEMPLATES.get_template("_outcome.html").render(
        response=ApiResponse(status=200, payload=payload)
    )


def test_primary_answer_renders_before_supporting_citations() -> None:
    html = _render(
        {
            "disposition": "answered",
            "source": "guidance",
            "primary_answer": "A Vault cluster spans availability zones.",
            "citations": [
                {
                    "url": "https://developer.hashicorp.com/patterns/vault/clustering#clustering",
                    "provenance": "validated-design",
                }
            ],
        }
    )

    assert "primary-answer" in html
    assert "A Vault cluster spans availability zones." in html
    assert html.index("primary-answer") < html.index("citations")
    assert 'class="claims"' not in html


def test_legacy_claims_outcomes_still_render() -> None:
    html = _render(
        {
            "disposition": "answered",
            "source": "guidance",
            "claims": [
                {
                    "statement": "A Vault cluster spans availability zones.",
                    "citations": [
                        "https://developer.hashicorp.com/patterns/vault/clustering#clustering"
                    ],
                }
            ],
        }
    )

    assert "A Vault cluster spans availability zones." in html
    assert 'class="claims"' in html


def test_fenced_code_renders_as_a_code_panel_not_a_prose_blob() -> None:
    html = _render(
        {
            "disposition": "answered",
            "source": "guidance",
            "primary_answer": (
                "Here is a sketch grounded in the cited section:\n\n"
                '```hcl\nresource "aws_instance" "example" {}\n```\n\n'
                "Adjust the instance type for your estate."
            ),
            "citations": [
                {
                    "url": "https://developer.hashicorp.com/patterns/vault/clustering#clustering",
                    "provenance": "validated-design",
                }
            ],
        }
    )

    assert 'class="answer-code-frame"' in html
    assert 'class="answer-code"' in html
    assert 'data-lang="hcl"' in html
    assert "aws_instance" in html
    assert 'class="tok-keyword"' in html
    assert "```" not in html
    assert "primary-answer-prose" in html
    assert "Here is a sketch" in html
    assert 'data-copy-scope="answer"' in html
    assert 'data-copy-scope="code"' in html


def test_answer_segments_splits_fences_without_inventing_structure() -> None:
    segments = answer_segments("Intro.\n\n```hcl\nfoo = 1\n```\n\nOutro.")
    assert [s["kind"] for s in segments] == ["prose", "code", "prose"]
    assert segments[1]["lang"] == "hcl"
    assert segments[1]["text"] == "foo = 1"


def test_primary_answer_prose_renders_model_bold_and_escapes_html() -> None:
    html = _render(
        {
            "disposition": "answered",
            "source": "guidance",
            "primary_answer": (
                "**Prerequisites to provision before writing/applying the template** "
                "(from the AWS platform guidance):\n\n"
                "Use `terraform init` after you obtain the module.\n"
                "<script>alert(1)</script>"
            ),
            "citations": [
                {
                    "url": "https://developer.hashicorp.com/patterns/vault/clustering#clustering",
                    "provenance": "validated-design",
                }
            ],
        }
    )

    assert (
        "<strong>Prerequisites to provision before writing/applying the template</strong>" in html
    )
    assert "<code>terraform init</code>" in html
    assert "**Prerequisites" not in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_answer_markup_leaves_unmatched_markers_visible() -> None:
    rendered = str(answer_markup("half **open and `unclosed"))
    assert "**open" in rendered
    assert "`unclosed" in rendered
    assert "<strong>" not in rendered
