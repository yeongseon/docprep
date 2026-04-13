from __future__ import annotations

from collections.abc import Callable
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
    extract_structural_annotations,
    structure_types_for_range,
)

TokenCounter = Callable[[str], int]

_PARAGRAPH_SPLIT = re.compile(r"\n\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class _ChunkRange:
    start: int
    end: int


class TokenChunker:
    def __init__(
        self,
        *,
        max_tokens: int = 512,
        overlap_tokens: int = 0,
        token_counter: TokenCounter | None = None,
    ) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if overlap_tokens < 0:
            raise ValueError("overlap_tokens must be >= 0")
        if overlap_tokens >= max_tokens:
            raise ValueError("overlap_tokens must be < max_tokens")
        self._max_tokens = max_tokens
        self._overlap_tokens = overlap_tokens
        self._counter: TokenCounter = (
            token_counter if token_counter is not None else _default_token_counter
        )

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

            structural_annotations = extract_structural_annotations(text)
            ranges = self._split_ranges(text)
            previous_base_text = ""
            for section_chunk_idx, chunk_range in enumerate(ranges):
                base_text = text[chunk_range.start : chunk_range.end]
                overlap = self._overlap_suffix(previous_base_text)
                if overlap and base_text:
                    joiner = ""
                    if (
                        chunk_range.start > 0
                        and text[chunk_range.start - 1].isspace()
                        and not overlap[-1].isspace()
                    ):
                        joiner = " "
                    fragment = overlap + joiner + base_text
                else:
                    fragment = base_text
                if not base_text.strip() or not fragment.strip():
                    continue

                c_hash = compute_content_hash(fragment)
                c_anchor = compute_chunk_anchor(section.anchor, section_chunk_idx)
                cid = chunk_id(document.id, c_anchor)
                structure_types = structure_types_for_range(
                    structural_annotations,
                    chunk_range.start,
                    chunk_range.end,
                )
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
                        token_count=self._count_tokens(fragment),
                        heading_path=section.heading_path,
                        lineage=section.lineage,
                        structure_types=structure_types,
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
            if self._count_tokens(remaining) <= self._max_tokens:
                end = _rstrip_index(text, start, len(text))
                if end > start:
                    ranges.append(_ChunkRange(start=start, end=end))
                break

            split_point = self._find_split_point(remaining)
            if split_point <= 0:
                split_point = max(1, self._max_prefix_within_budget(remaining, self._max_tokens))

            end = min(start + split_point, len(text))
            trimmed_end = _rstrip_index(text, start, end)
            if trimmed_end > start:
                ranges.append(_ChunkRange(start=start, end=trimmed_end))
            next_start = _lstrip_index(text, end)
            if next_start <= start:
                next_start = start + 1
            start = next_start

        return ranges

    def _find_split_point(self, text: str) -> int:
        context = _analyze_markdown(text)
        prefix_cache: dict[int, int] = {}

        def fits(end: int) -> bool:
            if end <= 0:
                return False
            if end not in prefix_cache:
                prefix_cache[end] = self._count_tokens(text[:end])
            return prefix_cache[end] <= self._max_tokens

        best = 0
        for match in _PARAGRAPH_SPLIT.finditer(text):
            candidate = match.start()
            if candidate > 0 and _is_safe_boundary(candidate, context) and fits(candidate):
                best = candidate
        if best > 0:
            return best

        for candidate in context.markdown_boundaries:
            if candidate > 0 and _is_safe_boundary(candidate, context) and fits(candidate):
                best = candidate
        if best > 0:
            return best

        for idx, char in enumerate(text):
            if char == "\n" and idx > 0 and _is_safe_boundary(idx, context) and fits(idx):
                best = idx
        if best > 0:
            return best

        best_sentence = 0
        for match in _SENTENCE_SPLIT.finditer(text):
            candidate = match.end()
            if _is_safe_boundary(candidate, context) and fits(candidate):
                best_sentence = candidate
        if best_sentence > 0:
            return best_sentence

        return self._hard_split_point(text, context)

    def _hard_split_point(self, text: str, context: _MarkdownContext) -> int:
        limit = self._max_prefix_within_budget(text, self._max_tokens)
        if limit <= 0:
            return 1
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

    def _overlap_suffix(self, text: str) -> str:
        if self._overlap_tokens <= 0 or not text:
            return ""
        if self._count_tokens(text) <= self._overlap_tokens:
            return text

        low = 0
        high = len(text)
        while low < high:
            mid = (low + high) // 2
            if self._count_tokens(text[mid:]) <= self._overlap_tokens:
                high = mid
            else:
                low = mid + 1
        while low < len(text) and text[low].isspace():
            low += 1
        return text[low:]

    def _max_prefix_within_budget(self, text: str, budget: int) -> int:
        low = 0
        high = len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if self._count_tokens(text[:mid]) <= budget:
                low = mid
            else:
                high = mid - 1
        return low

    def _count_tokens(self, text: str) -> int:
        count = self._counter(text)
        return count if count >= 0 else 0


def _default_token_counter(text: str) -> int:
    return len(text.split())
