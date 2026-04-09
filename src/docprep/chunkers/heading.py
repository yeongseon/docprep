"""HeadingChunker — splits a document into heading-delimited sections."""

from __future__ import annotations

from dataclasses import replace
import re

from docprep.exceptions import ChunkError
from docprep.ids import section_id
from docprep.models.domain import Document, Section

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class HeadingChunker:
    """Splits a document body into sections based on Markdown headings.

    Populates ``document.sections``; leaves ``document.chunks`` empty.
    A root section (heading=None, heading_level=0) is created only when
    non-empty content precedes the first heading.
    """

    def chunk(self, document: Document) -> Document:
        if document.sections:
            raise ChunkError("Document already has sections; HeadingChunker expects none.")

        body = document.body_markdown
        if not body.strip():
            return document

        raw_sections = self._split_by_headings(body)
        sections = self._build_sections(document.id, raw_sections)
        return replace(document, sections=tuple(sections))

    def _split_by_headings(self, body: str) -> list[tuple[int, str | None, str]]:
        """Return list of (heading_level, heading_text | None, content_markdown)."""
        parts: list[tuple[int, str | None, str]] = []
        last_end = 0

        for match in _HEADING_RE.finditer(body):
            pre_content = body[last_end : match.start()].strip()
            if pre_content or not parts:
                if pre_content and not parts:
                    # Root section for content before first heading
                    parts.append((0, None, pre_content))
                elif pre_content and parts:
                    # Append trailing content to previous section
                    level, heading, existing = parts[-1]
                    merged = f"{existing}\n\n{pre_content}" if existing else pre_content
                    parts[-1] = (level, heading, merged)

            level = len(match.group(1))
            heading_text = match.group(2).strip()
            parts.append((level, heading_text, ""))
            last_end = match.end()

        # Content after the last heading (or entire body if no headings)
        trailing = body[last_end:].strip()
        if parts:
            if trailing:
                level, heading, existing = parts[-1]
                merged = f"{existing}\n\n{trailing}" if existing else trailing
                parts[-1] = (level, heading, merged)
        elif trailing:
            # No headings at all — single root section
            parts.append((0, None, trailing))

        return parts

    def _build_sections(
        self,
        doc_id: object,
        raw_sections: list[tuple[int, str | None, str]],
    ) -> list[Section]:
        sections: list[Section] = []
        # heading_stack tracks (level, heading_text, section_id) for building paths
        heading_stack: list[tuple[int, str, object]] = []

        for order_index, (level, heading, content) in enumerate(raw_sections):
            sid = section_id(doc_id, order_index)  # type: ignore[arg-type]

            if heading is not None:
                # Pop stack entries at same or deeper level
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, heading, sid))

            heading_path = tuple(h[1] for h in heading_stack)
            lineage = tuple(str(h[2]) for h in heading_stack)

            parent_id = heading_stack[-2][2] if len(heading_stack) >= 2 else None

            sections.append(
                Section(
                    id=sid,
                    document_id=doc_id,  # type: ignore[arg-type]
                    order_index=order_index,
                    parent_id=parent_id,  # type: ignore[arg-type]
                    heading=heading,
                    heading_level=level,
                    heading_path=heading_path,
                    lineage=lineage,
                    content_markdown=content,
                )
            )

        return sections
