"""SizeChunker — splits sections into sized text chunks."""

from __future__ import annotations

from dataclasses import replace
import re

from docprep.exceptions import ChunkError
from docprep.ids import chunk_id
from docprep.models.domain import Chunk, Document

# Greedy split order: paragraph → newline → sentence → hard
_PARAGRAPH_SPLIT = re.compile(r"\n\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class SizeChunker:
    """Splits document sections into sized chunks.

    Requires ``document.sections`` to be populated (e.g. by HeadingChunker).
    Uses a greedy split strategy: paragraph → newline → sentence → hard split.
    No overlap between chunks.
    """

    def __init__(self, *, max_chars: int = 1500) -> None:
        if max_chars < 1:
            raise ValueError("max_chars must be >= 1")
        self._max_chars = max_chars

    def chunk(self, document: Document) -> Document:
        if not document.sections:
            raise ChunkError("Document has no sections; run HeadingChunker first.")
        if document.chunks:
            raise ChunkError("Document already has chunks.")

        all_chunks: list[Chunk] = []
        global_order = 0

        for section in document.sections:
            text = section.content_markdown.strip()
            if not text:
                continue

            fragments = self._split_text(text)
            for section_chunk_idx, fragment in enumerate(fragments):
                cid = chunk_id(section.id, section_chunk_idx)
                all_chunks.append(
                    Chunk(
                        id=cid,
                        document_id=document.id,
                        section_id=section.id,
                        order_index=global_order,
                        section_chunk_index=section_chunk_idx,
                        content_text=fragment,
                        heading_path=section.heading_path,
                        lineage=section.lineage,
                    )
                )
                global_order += 1

        return replace(document, chunks=tuple(all_chunks))

    def _split_text(self, text: str) -> list[str]:
        if len(text) <= self._max_chars:
            return [text]

        chunks: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= self._max_chars:
                chunks.append(remaining)
                break

            split_point = self._find_split_point(remaining)
            chunks.append(remaining[:split_point].rstrip())
            remaining = remaining[split_point:].lstrip()

        return [c for c in chunks if c]

    def _find_split_point(self, text: str) -> int:
        limit = self._max_chars

        # 1) paragraph boundary
        for match in _PARAGRAPH_SPLIT.finditer(text):
            if match.start() > 0 and match.start() <= limit:
                best = match.start()
            elif match.start() > limit:
                break
        else:
            best = 0
        if best > 0:
            return best

        # 2) newline boundary
        idx = text.rfind("\n", 0, limit)
        if idx > 0:
            return idx

        # 3) sentence boundary
        best_sentence = 0
        for match in _SENTENCE_SPLIT.finditer(text):
            if match.end() <= limit:
                best_sentence = match.end()
            else:
                break
        if best_sentence > 0:
            return best_sentence

        # 4) hard split at max_chars
        return limit
