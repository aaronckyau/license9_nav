from __future__ import annotations

import re
from dataclasses import dataclass

import bleach
import markdown


@dataclass(frozen=True, slots=True)
class InlineSegment:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True, slots=True)
class CommentaryBlock:
    kind: str
    segments: list[InlineSegment]


INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|(?<!\*)\*[^*]+\*(?!\*))")


def inline_segments(text: str) -> list[InlineSegment]:
    segments: list[InlineSegment] = []
    cursor = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > cursor:
            segments.append(InlineSegment(text[cursor : match.start()]))
        token = match.group(0)
        if token.startswith("**"):
            segments.append(InlineSegment(token[2:-2], bold=True))
        else:
            segments.append(InlineSegment(token[1:-1], italic=True))
        cursor = match.end()
    if cursor < len(text):
        segments.append(InlineSegment(text[cursor:]))
    return segments or [InlineSegment("")]


def parse_commentary(value: str) -> list[CommentaryBlock]:
    blocks: list[CommentaryBlock] = []
    for raw_line in value.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(("- ", "* ")):
            blocks.append(CommentaryBlock("bullet", inline_segments(line[2:].strip())))
        elif re.match(r"^\d+[.)]\s+", line):
            blocks.append(
                CommentaryBlock("number", inline_segments(re.sub(r"^\d+[.)]\s+", "", line)))
            )
        else:
            blocks.append(CommentaryBlock("paragraph", inline_segments(line)))
    return blocks


def render_safe_html(value: str) -> str:
    rendered = markdown.markdown(value, extensions=[])
    return bleach.clean(
        rendered,
        tags={"p", "strong", "em", "ul", "ol", "li", "br"},
        attributes={},
        protocols=set(),
        strip=True,
    )
