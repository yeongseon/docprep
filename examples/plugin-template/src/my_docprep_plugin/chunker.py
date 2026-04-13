"""Sentence-based chunker plugin for docprep."""

from __future__ import annotations

import hashlib
import re
import uuid

from docprep.ids import DOCPREP_NAMESPACE
from docprep.models.domain import Chunk, Document


class SentenceChunker:
    """Splits document sections into one chunk per sentence.

    Usage in docprep.toml:

        [[chunkers]]
        type = "sentence"
    """

    # Splits on sentence-ending punctuation followed by whitespace or end-of-string.
    _SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

    def chunk(self, document: Document) -> Document:
        if not document.sections:
            return document

        chunks: list[Chunk] = []
        chunk_index = 0

        for section in document.sections:
            if not section.content_markdown:
                continue

            sentences = [
                s.strip() for s in self._SENTENCE_RE.split(section.content_markdown) if s.strip()
            ]

            for sent_idx, sentence in enumerate(sentences):
                content_hash = hashlib.sha256(sentence.encode("utf-8")).hexdigest()[:16]
                anchor = f"{section.anchor}:s{sent_idx}"
                chunk_id = uuid.uuid5(
                    DOCPREP_NAMESPACE,
                    f"{document.id}:chunk:{anchor}",
                )

                chunks.append(
                    Chunk(
                        id=chunk_id,
                        document_id=document.id,
                        section_id=section.id,
                        order_index=chunk_index,
                        section_chunk_index=sent_idx,
                        anchor=anchor,
                        content_hash=content_hash,
                        content_text=sentence,
                        char_start=0,
                        char_end=len(sentence),
                        heading_path=section.heading_path,
                        lineage=section.lineage,
                    )
                )
                chunk_index += 1

        return Document(
            id=document.id,
            source_uri=document.source_uri,
            title=document.title,
            source_checksum=document.source_checksum,
            source_type=document.source_type,
            frontmatter=document.frontmatter,
            source_metadata=document.source_metadata,
            body_markdown=document.body_markdown,
            structural_annotations=document.structural_annotations,
            sections=document.sections,
            chunks=tuple(chunks),
        )
