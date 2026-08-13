# SPDX-License-Identifier: Apache-2.0
"""Portal Ask code highlighting escapes first and colours known languages only."""

from __future__ import annotations

from surfaces.portal.highlight import highlight_code


def test_hcl_keywords_and_strings_are_marked_and_html_is_escaped() -> None:
    html = str(
        highlight_code(
            'resource "aws_instance" "example" {\n  # note\n  count = 1\n}\n<script>',
            "hcl",
        )
    )

    assert 'class="tok-keyword">resource</span>' in html
    assert 'class="tok-string">' in html and "aws_instance" in html
    assert 'class="tok-comment"># note</span>' in html
    assert 'class="tok-number">1</span>' in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_unknown_language_is_escaped_plain_text() -> None:
    html = str(highlight_code('resource "x" {}', "ruby"))
    assert "tok-keyword" not in html
    assert "resource" in html


def test_shell_comments_are_marked() -> None:
    html = str(highlight_code("terraform init\n# apply later", "shell"))
    assert 'class="tok-comment"># apply later</span>' in html
