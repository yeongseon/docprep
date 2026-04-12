from __future__ import annotations

from dataclasses import dataclass, replace
import re

from ..exceptions import ChunkError
from ..ids import (
    chunk_anchor as compute_chunk_anchor,
)
from ..ids import (
    chunk_id,
)
from ..ids import (
    content_hash as compute_content_hash,
)
from ..models.domain import Chunk, Document
from ._markdown import (
    _analyze_markdown,
    _is_safe_boundary,
    _lstrip_index,
    _MarkdownContext,
    _rstrip_index,
    _trim_range,
)

_PARAGRAPH_SPLIT = re.compile(r"\n\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class _ChunkRange:
    start: int
    end: int


class SizeChunker:
    def __init__(
        self,
        *,
        max_chars: int = 1500,
        overlap_chars: int = 0,
        min_chars: int = 0,
    ) -> None:
        if max_chars < 1:
            raise ValueError("max_chars must be >= 1")
        if overlap_chars < 0:
            raise ValueError("overlap_chars must be >= 0")
        if min_chars < 0:
            raise ValueError("min_chars must be >= 0")
        if overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be < max_chars")
        self._max_chars = max_chars
        self._overlap_chars = overlap_chars
        self._min_chars = min_chars

    def chunk(self, document: Document) -> Document:
        if not document.sections:
            raise ChunkError("Document has no sections; run HeadingChunker first.")
        if document.chunks:
            raise ChunkError("Document already has chunks.")

        all_chunks: list[Chunk] = []
        global_order = 0

        for section in document.sections:
            text = section.content_markdown
            if not text.strip():
                continue

            ranges = self._split_ranges(text)
            ranges = self._merge_small_ranges(text, ranges)
            dup_counts: dict[tuple[str, str], int] = {}
            previous_base_text = ""
            for section_chunk_idx, chunk_range in enumerate(ranges):
                base_text = text[chunk_range.start : chunk_range.end]
                fragment = base_text
                if self._overlap_chars > 0 and previous_base_text:
                    overlap = previous_base_text[-self._overlap_chars :]
                    if overlap and base_text:
                        fragment = overlap + base_text
                if not base_text.strip() or not fragment.strip():
                    continue

                c_hash = compute_content_hash(fragment)
                c_anchor = compute_chunk_anchor(section.anchor, c_hash, dup_counts)
                cid = chunk_id(document.id, c_anchor)
                all_chunks.append(
                    Chunk(
                        id=cid,
                        document_id=document.id,
                        section_id=section.id,
                        order_index=global_order,
                        section_chunk_index=section_chunk_idx,
                        anchor=c_anchor,
                        content_hash=c_hash,
                        content_text=fragment,
                        char_start=chunk_range.start,
                        char_end=chunk_range.end,
                        heading_path=section.heading_path,
                        lineage=section.lineage,
                    )
                )
                global_order += 1
                previous_base_text = base_text

        return replace(document, chunks=tuple(all_chunks))

    def _split_ranges(self, text: str) -> list[_ChunkRange]:
        start = _lstrip_index(text, 0)
        if start >= len(text):
            return []

        ranges: list[_ChunkRange] = []
        while start < len(text):
            remaining = text[start:]
            if len(remaining) <= self._max_chars:
                end = _rstrip_index(text, start, len(text))
                if end > start:
                    ranges.append(_ChunkRange(start=start, end=end))
                break

            split_point = self._find_split_point(remaining)
            if split_point <= 0:
                split_point = min(self._max_chars, len(remaining))
            end = min(start + split_point, len(text))
            trimmed_end = _rstrip_index(text, start, end)
            if trimmed_end > start:
                ranges.append(_ChunkRange(start=start, end=trimmed_end))
            next_start = _lstrip_index(text, end)
            if next_start <= start:
                next_start = start + 1
            start = next_start

        return ranges

    def _merge_small_ranges(self, text: str, ranges: list[_ChunkRange]) -> list[_ChunkRange]:
        if self._min_chars <= 0 or len(ranges) < 2:
            return ranges

        merged = list(ranges)
        i = 0
        while i < len(merged):
            current = merged[i]
            current_len = current.end - current.start
            if current_len >= self._min_chars:
                i += 1
                continue

            if i > 0:
                prev = merged[i - 1]
                start, end = _trim_range(text, prev.start, current.end)
                merged[i - 1] = _ChunkRange(start=start, end=end)
                del merged[i]
                i = max(i - 1, 0)
                continue

            if len(merged) > 1:
                nxt = merged[i + 1]
                start, end = _trim_range(text, current.start, nxt.end)
                merged[i] = _ChunkRange(start=start, end=end)
                del merged[i + 1]
                continue

            i += 1

        return [item for item in merged if item.end > item.start]

    def _find_split_point(self, text: str) -> int:
        limit = self._max_chars
        context = _analyze_markdown(text)

        best = 0
        for match in _PARAGRAPH_SPLIT.finditer(text):
            candidate = match.start()
            if candidate > 0 and candidate <= limit and _is_safe_boundary(candidate, context):
                best = match.start()
            elif candidate > limit:
                break
        if best > 0:
            return best

        for candidate in context.markdown_boundaries:
            if candidate > limit:
                break
            if candidate > 0 and _is_safe_boundary(candidate, context):
                best = candidate
        if best > 0:
            return best

        idx = text.rfind("\n", 0, limit)
        if idx > 0 and _is_safe_boundary(idx, context):
            return idx

        best_sentence = 0
        for match in _SENTENCE_SPLIT.finditer(text):
            candidate = match.end()
            if candidate <= limit and _is_safe_boundary(candidate, context):
                best_sentence = match.end()
            else:
                break
        if best_sentence > 0:
            return best_sentence

        return self._hard_split_point(text, limit, context)

    def _hard_split_point(self, text: str, limit: int, context: _MarkdownContext) -> int:
        if _is_safe_boundary(limit, context):
            return limit

        for start, end in context.protected_spans:
            if start < limit < end:
                return end

        for candidate in range(limit - 1, 0, -1):
            if _is_safe_boundary(candidate, context):
                return candidate

        for candidate in range(limit + 1, len(text) + 1):
            if _is_safe_boundary(candidate, context):
                return candidate

        return min(len(text), max(1, limit))
