"""Canonical, renderer-neutral representation of persisted answer Markdown."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Literal
from markdown_it import MarkdownIt

@dataclass(frozen=True)
class InlineText: text: str
@dataclass(frozen=True)
class InlineCode: text: str
@dataclass(frozen=True)
class Bold: children: list[object]
@dataclass(frozen=True)
class Italic: children: list[object]
@dataclass(frozen=True)
class Link: children: list[object]; href: str
@dataclass(frozen=True)
class CitationReference: reference_id: int
@dataclass(frozen=True)
class SoftBreak: pass
InlineNode = InlineText | InlineCode | Bold | Italic | Link | CitationReference | SoftBreak

@dataclass(frozen=True)
class HeadingBlock: level: int; text: str
@dataclass(frozen=True)
class ParagraphBlock: inline_nodes: list[InlineNode]
@dataclass(frozen=True)
class BulletListBlock:
    items: list[list[object]]
    nesting: int = 0
    task_states: list[bool | None] = field(default_factory=list)
@dataclass(frozen=True)
class NumberedListBlock: items: list[list[object]]; nesting: int = 0; start: int = 1
@dataclass(frozen=True)
class TableBlock: headers: list[str]; rows: list[list[str]]; alignments: list[str | None]
@dataclass(frozen=True)
class CodeBlock: code: str; language: str | None = None
@dataclass(frozen=True)
class QuoteBlock: blocks: list[object]
@dataclass(frozen=True)
class CalloutBlock: kind: str; title: str; blocks: list[object]
@dataclass(frozen=True)
class HorizontalRuleBlock: pass
@dataclass(frozen=True)
class PageBreakBlock: pass
Block = HeadingBlock | ParagraphBlock | BulletListBlock | NumberedListBlock | TableBlock | CodeBlock | QuoteBlock | CalloutBlock | HorizontalRuleBlock | PageBreakBlock

@dataclass(frozen=True)
class ExportSource:
    citation_number: int
    document_title: str
    page_number: int | None = None
    location: str | None = None
    repository: str | None = None
    safe_url: str | None = None

@dataclass(frozen=True)
class ExportDocument:
    title: str
    subtitle: str | None
    generated_at: datetime
    query: str | None
    context_metadata: dict[str, object]
    blocks: list[Block]
    citations: list[int]
    sources: list[ExportSource]
    footer_metadata: dict[str, str] = field(default_factory=dict)

_CITATION = re.compile(r"\[(\d+)\]")
_SAFE_SCHEMES = ("http://", "https://", "mailto:", "/")

class MarkdownExportParser:
    def __init__(self) -> None: self.markdown = MarkdownIt("commonmark", {"html": False, "linkify": False}).enable("table")

    def _inline(self, token) -> list[InlineNode]:
        result: list[InlineNode] = []
        stack: list[tuple[str, list[InlineNode], str | None]] = []
        current = result
        for child in token.children or []:
            if child.type == "text":
                cursor = 0
                for match in _CITATION.finditer(child.content):
                    if match.start() > cursor: current.append(InlineText(child.content[cursor:match.start()]))
                    current.append(CitationReference(int(match.group(1)))); cursor = match.end()
                if cursor < len(child.content): current.append(InlineText(child.content[cursor:]))
            elif child.type == "code_inline": current.append(InlineCode(child.content))
            elif child.type in {"softbreak", "hardbreak"}: current.append(SoftBreak())
            elif child.type in {"strong_open", "em_open", "link_open"}:
                href = child.attrGet("href") if child.type == "link_open" else None
                stack.append((child.type, current, href)); nested: list[InlineNode] = []; current = nested
            elif child.type in {"strong_close", "em_close", "link_close"} and stack:
                kind, parent, href = stack.pop(); wrapped: InlineNode
                if kind == "strong_open": wrapped = Bold(current)
                elif kind == "em_open": wrapped = Italic(current)
                else: wrapped = Link(current, href or "") if (href or "").startswith(_SAFE_SCHEMES) else InlineText("".join(getattr(x, "text", "") for x in current))
                current = parent; current.append(wrapped)
        return result

    def parse(self, markdown: str) -> list[Block]:
        tokens = self.markdown.parse(markdown); blocks: list[Block] = []; i = 0
        while i < len(tokens):
            token = tokens[i]
            if token.type == "heading_open" and i + 1 < len(tokens):
                blocks.append(HeadingBlock(int(token.tag[1]), tokens[i + 1].content)); i += 3; continue
            if token.type == "paragraph_open" and i + 1 < len(tokens):
                blocks.append(ParagraphBlock(self._inline(tokens[i + 1]))); i += 3; continue
            if token.type in {"fence", "code_block"}: blocks.append(CodeBlock(token.content, token.info.strip() or None)); i += 1; continue
            if token.type == "hr": blocks.append(HorizontalRuleBlock()); i += 1; continue
            if token.type in {"bullet_list_open", "ordered_list_open"}:
                close = "bullet_list_close" if token.type == "bullet_list_open" else "ordered_list_close"; depth = 1; j = i + 1; items: list[list[object]] = []; current: list[object] = []
                while j < len(tokens) and depth:
                    part = tokens[j]
                    if part.type == token.type: depth += 1
                    elif part.type == close: depth -= 1
                    elif depth == 1 and part.type == "list_item_open": current = []
                    elif depth == 1 and part.type == "inline": current.append(ParagraphBlock(self._inline(part)))
                    elif depth == 1 and part.type == "list_item_close": items.append(current)
                    j += 1
                if token.type == "bullet_list_open":
                    task_states = [self._extract_task_state(item) for item in items]
                    blocks.append(BulletListBlock(items, task_states=task_states))
                else:
                    blocks.append(NumberedListBlock(items, start=int(token.attrGet("start") or 1)))
                i = j; continue
            if token.type == "blockquote_open":
                j = i + 1; inner = []
                while j < len(tokens) and tokens[j].type != "blockquote_close":
                    if tokens[j].type == "inline": inner.append(ParagraphBlock(self._inline(tokens[j])))
                    j += 1
                blocks.append(QuoteBlock(inner)); i = j + 1; continue
            if token.type == "table_open":
                j = i + 1; matrix: list[list[str]] = []; row: list[str] = []
                while j < len(tokens) and tokens[j].type != "table_close":
                    if tokens[j].type == "tr_open": row = []
                    elif tokens[j].type == "inline": row.append(tokens[j].content)
                    elif tokens[j].type == "tr_close": matrix.append(row)
                    j += 1
                blocks.append(TableBlock(matrix[0] if matrix else [], matrix[1:] if len(matrix) > 1 else [], [None] * len(matrix[0] if matrix else []))); i = j + 1; continue
            i += 1
        return blocks

    @staticmethod
    def _extract_task_state(item: list[object]) -> bool | None:
        if not item or not isinstance(item[0], ParagraphBlock) or not item[0].inline_nodes:
            return None
        first = item[0].inline_nodes[0]
        if not isinstance(first, InlineText):
            return None
        match = re.match(r"^\s*\[([ xX])\]\s+", first.text)
        if not match:
            return None
        replacement = first.text[match.end():]
        nodes = list(item[0].inline_nodes)
        if replacement:
            nodes[0] = InlineText(replacement)
        else:
            nodes.pop(0)
        item[0] = ParagraphBlock(nodes)
        return match.group(1).casefold() == "x"

def cited_reference_ids(markdown: str) -> list[int]: return list(dict.fromkeys(int(value) for value in _CITATION.findall(markdown)))
