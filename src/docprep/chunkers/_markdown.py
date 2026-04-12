from __future__ import annotations

from dataclasses import dataclass
import re

from ..models.domain import StructuralAnnotation, StructureKind

_PARAGRAPH_SPLIT = re.compile(r"\n\n+")
_FENCE_RE = re.compile(r"^ {0,3}([`~]{3,}).*$")
_TOP_LEVEL_LIST_RE = re.compile(r"^ {0,3}(?:[-+*]|\d+[.)])\s+")


@dataclass(frozen=True, slots=True)
class _MarkdownContext:
    protected_spans: tuple[tuple[int, int], ...]
    markdown_boundaries: tuple[int, ...]


def _analyze_markdown(text: str) -> _MarkdownContext:
    line_spans = _line_spans(text)
    protected: list[tuple[int, int]] = []
    boundaries: set[int] = set()

    fence_spans = _fence_spans(line_spans, text_len=len(text))
    protected.extend(fence_spans)
    for start, end in fence_spans:
        boundaries.add(start)
        boundaries.add(end)

    table_info = _table_spans_and_boundaries(line_spans)
    protected.extend(table_info[0])
    boundaries.update(table_info[1])

    list_info = _list_item_spans_and_boundaries(line_spans)
    protected.extend(list_info[0])
    boundaries.update(list_info[1])

    heading_span = _heading_first_paragraph_span(text)
    if heading_span is not None:
        protected.append(heading_span)

    deduped = _dedupe_and_sort_spans(protected)
    ordered_boundaries = tuple(sorted(pos for pos in boundaries if 0 < pos < len(text)))
    return _MarkdownContext(protected_spans=deduped, markdown_boundaries=ordered_boundaries)


def _is_safe_boundary(pos: int, context: _MarkdownContext) -> bool:
    if pos <= 0:
        return False
    for start, end in context.protected_spans:
        if start < pos < end:
            return False
    return True


def _line_spans(text: str) -> list[tuple[int, int, str, bool]]:
    spans: list[tuple[int, int, str, bool]] = []
    start = 0
    for line in text.splitlines(keepends=True):
        end = start + len(line)
        has_newline = line.endswith("\n")
        content = line[:-1] if has_newline else line
        spans.append((start, end, content, has_newline))
        start = end
    if not spans:
        spans.append((0, len(text), text, False))
    return spans


def _fence_spans(
    line_spans: list[tuple[int, int, str, bool]],
    *,
    text_len: int,
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    fence_start: int | None = None
    fence_char: str | None = None
    fence_len = 0

    for line_start, line_end, line_content, _ in line_spans:
        match = _FENCE_RE.match(line_content)
        if match is None:
            continue

        marker = match.group(1)
        marker_char = marker[0]
        marker_len = len(marker)

        if fence_start is None:
            fence_start = line_start
            fence_char = marker_char
            fence_len = marker_len
            continue

        if marker_char == fence_char and marker_len >= fence_len:
            spans.append((fence_start, line_end))
            fence_start = None
            fence_char = None
            fence_len = 0

    if fence_start is not None:
        spans.append((fence_start, text_len))
    return spans


def _table_spans_and_boundaries(
    line_spans: list[tuple[int, int, str, bool]],
) -> tuple[list[tuple[int, int]], set[int]]:
    protected: list[tuple[int, int]] = []
    boundaries: set[int] = set()

    in_table = False
    table_start = 0
    last_row_boundary = 0
    for line_start, line_end, content, has_newline in line_spans:
        is_table_row = _is_table_row(content)
        row_boundary = line_end - 1 if has_newline else line_end
        if is_table_row:
            if not in_table:
                in_table = True
                table_start = line_start
            protected.append((line_start, row_boundary))
            boundaries.add(row_boundary)
            last_row_boundary = row_boundary
            continue

        if in_table:
            boundaries.add(table_start)
            boundaries.add(last_row_boundary)
            in_table = False

    if in_table:
        boundaries.add(table_start)
        boundaries.add(last_row_boundary)

    return protected, boundaries


def _list_item_spans_and_boundaries(
    line_spans: list[tuple[int, int, str, bool]],
) -> tuple[list[tuple[int, int]], set[int]]:
    protected: list[tuple[int, int]] = []
    boundaries: set[int] = set()

    item_starts = [
        start for start, _, content, _ in line_spans if _TOP_LEVEL_LIST_RE.match(content)
    ]
    text_end = line_spans[-1][1] if line_spans else 0
    for index, item_start in enumerate(item_starts):
        item_end = item_starts[index + 1] if index + 1 < len(item_starts) else text_end
        if item_end > item_start:
            protected.append((item_start, item_end))
            boundaries.add(item_end)

    return protected, boundaries


def _heading_first_paragraph_span(text: str) -> tuple[int, int] | None:
    lines = text.splitlines(keepends=True)
    if not lines:
        return None

    first_line = lines[0].rstrip("\n")
    if not re.match(r"^ {0,3}#{1,6}\s+.+$", first_line):
        return None

    heading_end = len(lines[0])
    para_start = heading_end
    while para_start < len(text) and text[para_start] in "\n\r\t ":
        para_start += 1
    if para_start >= len(text):
        return None

    paragraph_break = _PARAGRAPH_SPLIT.search(text, para_start)
    if paragraph_break is None:
        return (0, len(text))
    return (0, paragraph_break.start())


def _is_table_row(content: str) -> bool:
    stripped = content.strip()
    return "|" in stripped and stripped != ""


def _dedupe_and_sort_spans(spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    normalized = sorted({(start, end) for start, end in spans if end > start})
    return tuple(normalized)


def _lstrip_index(text: str, start: int) -> int:
    idx = start
    while idx < len(text) and text[idx].isspace():
        idx += 1
    return idx


def _rstrip_index(text: str, start: int, end: int) -> int:
    idx = end
    while idx > start and text[idx - 1].isspace():
        idx -= 1
    return idx


def _trim_range(text: str, start: int, end: int) -> tuple[int, int]:
    trimmed_start = _lstrip_index(text, start)
    trimmed_end = _rstrip_index(text, trimmed_start, end)
    return trimmed_start, trimmed_end


def extract_structural_annotations(text: str) -> tuple[StructuralAnnotation, ...]:
    """Extract structural annotations (code fences, tables, lists) from markdown text."""

    if not text:
        return ()

    line_spans = _line_spans(text)

    annotations: list[StructuralAnnotation] = []
    for start, end in _fence_spans(line_spans, text_len=len(text)):
        annotations.append(
            StructuralAnnotation(
                kind=StructureKind.CODE_FENCE,
                char_start=start,
                char_end=end,
            )
        )

    table_row_spans, _ = _table_spans_and_boundaries(line_spans)
    for start, end in _merge_row_like_spans(table_row_spans):
        annotations.append(
            StructuralAnnotation(
                kind=StructureKind.TABLE,
                char_start=start,
                char_end=end,
            )
        )

    list_item_spans, _ = _list_item_spans_and_boundaries(line_spans)
    for start, end in _merge_touching_spans(list_item_spans):
        annotations.append(
            StructuralAnnotation(
                kind=StructureKind.LIST,
                char_start=start,
                char_end=end,
            )
        )

    return tuple(
        sorted(
            annotations,
            key=lambda item: (item.char_start, item.char_end, item.kind.value),
        )
    )


def structure_types_for_range(
    annotations: tuple[StructuralAnnotation, ...],
    start: int,
    end: int,
) -> tuple[str, ...]:
    """Return sorted unique structure type strings for annotations overlapping [start, end)."""

    if start >= end:
        return ()

    structure_types = {
        annotation.kind.value
        for annotation in annotations
        if annotation.char_start < end and annotation.char_end > start
    }
    return tuple(sorted(structure_types))


def _merge_row_like_spans(spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    if not spans:
        return ()

    merged: list[tuple[int, int]] = []
    current_start, current_end = spans[0]
    for next_start, next_end in spans[1:]:
        if next_start <= current_end + 1:
            current_end = max(current_end, next_end)
            continue
        merged.append((current_start, current_end))
        current_start, current_end = next_start, next_end
    merged.append((current_start, current_end))
    return tuple(merged)


def _merge_touching_spans(spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    if not spans:
        return ()

    merged: list[tuple[int, int]] = []
    current_start, current_end = spans[0]
    for next_start, next_end in spans[1:]:
        if next_start <= current_end:
            current_end = max(current_end, next_end)
            continue
        merged.append((current_start, current_end))
        current_start, current_end = next_start, next_end
    merged.append((current_start, current_end))
    return tuple(merged)
