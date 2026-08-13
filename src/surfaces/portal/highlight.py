# SPDX-License-Identifier: Apache-2.0
"""Lightweight syntax colouring for Ask code panels — presentation only.

**Not a language server and not a dependency.** The portal may not fetch a highlighter from
the network (identity / offline rule), and adding Pygments would be a core dependency for a
display concern. This escapes first, then wraps a few token classes for the languages Ask
actually fences (HCL/Terraform, shell, JSON). Unknown languages render as escaped plain text.
"""

from __future__ import annotations

import re
from typing import Final

from markupsafe import Markup, escape

_HCL_KEYWORDS: Final[frozenset[str]] = frozenset(
    {
        "resource",
        "module",
        "variable",
        "output",
        "provider",
        "terraform",
        "locals",
        "data",
        "true",
        "false",
        "null",
        "for",
        "in",
        "if",
        "else",
        "endif",
        "endfor",
    }
)

#: HCL / Terraform — comments, strings, keywords, numbers, bare words, punctuation.
_HCL_TOKEN: Final[re.Pattern[str]] = re.compile(
    r"(#.*?$)|(\"(?:\\.|[^\"\\])*\")|"
    r"(\b(?:resource|module|variable|output|provider|terraform|locals|data|"
    r"true|false|null|for|in|if|else|endif|endfor)\b)|"
    r"(\b\d+(?:\.\d+)?\b)|([{}[\]=(),])|(\s+)|([^\s#\"{}[\]=(),]+)",
    re.MULTILINE,
)

#: Shell — comments, quoted strings, trailing operators, words.
_SHELL_TOKEN: Final[re.Pattern[str]] = re.compile(
    r"(#.*?$)|(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')|"
    r"(\b(?:if|then|else|fi|for|do|done|in|export|set|echo|cd|source)\b)|"
    r"([|&;<>]+)|(\s+)|([^\s#\"'|&;<>]+)",
    re.MULTILINE,
)

#: JSON — strings, literals, numbers, punctuation.
_JSON_TOKEN: Final[re.Pattern[str]] = re.compile(
    r"(\"(?:\\.|[^\"\\])*\")|(\b(?:true|false|null)\b)|"
    r"(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|([{}\[\]:,])|(\s+)|([^\s\"{}\[\]:,]+)",
)


def _span(kind: str, text: str) -> str:
    return f'<span class="tok-{kind}">{escape(text)}</span>'


def _paint_hcl(raw: str) -> str:
    parts: list[str] = []
    for match in _HCL_TOKEN.finditer(raw):
        comment, string, keyword, number, punct, space, word = match.groups()
        if comment is not None:
            parts.append(_span("comment", comment))
        elif string is not None:
            parts.append(_span("string", string))
        elif keyword is not None:
            parts.append(_span("keyword", keyword))
        elif number is not None:
            parts.append(_span("number", number))
        elif punct is not None:
            parts.append(_span("punct", punct))
        elif space is not None:
            parts.append(escape(space))
        elif word is not None:
            # Attribute-ish keys before '=' are handled as words; HCL keywords already caught.
            cls = "keyword" if word in _HCL_KEYWORDS else "name"
            parts.append(_span(cls, word))
    return "".join(parts)


def _paint_shell(raw: str) -> str:
    parts: list[str] = []
    for match in _SHELL_TOKEN.finditer(raw):
        comment, string, keyword, op, space, word = match.groups()
        if comment is not None:
            parts.append(_span("comment", comment))
        elif string is not None:
            parts.append(_span("string", string))
        elif keyword is not None:
            parts.append(_span("keyword", keyword))
        elif op is not None:
            parts.append(_span("punct", op))
        elif space is not None:
            parts.append(escape(space))
        elif word is not None:
            parts.append(_span("name", word))
    return "".join(parts)


def _paint_json(raw: str) -> str:
    parts: list[str] = []
    for match in _JSON_TOKEN.finditer(raw):
        string, literal, number, punct, space, other = match.groups()
        if string is not None:
            # JSON keys and string values look the same lexically; colour as string.
            parts.append(_span("string", string))
        elif literal is not None:
            parts.append(_span("keyword", literal))
        elif number is not None:
            parts.append(_span("number", number))
        elif punct is not None:
            parts.append(_span("punct", punct))
        elif space is not None:
            parts.append(escape(space))
        elif other is not None:
            parts.append(_span("name", other))
    return "".join(parts)


def highlight_code(text: object, lang: object = "") -> Markup:
    """Escape ``text`` and wrap tokens for ``lang`` when we know how."""
    raw = str(text or "")
    if not raw:
        return Markup("")
    kind = str(lang or "").strip().lower()
    if kind in {"hcl", "terraform", "tf"}:
        return Markup(_paint_hcl(raw))
    if kind in {"shell", "bash", "sh", "zsh"}:
        return Markup(_paint_shell(raw))
    if kind == "json":
        return Markup(_paint_json(raw))
    return Markup(str(escape(raw)))


__all__ = ["highlight_code"]
