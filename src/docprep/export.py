"""Vector-ready export — build VectorRecords from Documents."""

from __future__ import annotations

from docprep.models.domain import Chunk, Document, VectorRecord


def build_vector_records(documents: tuple[Document, ...]) -> tuple[VectorRecord, ...]:
    records: list[VectorRecord] = []

    for doc in documents:
        for chunk in doc.chunks:
            text = _build_text(doc.title, chunk)
            metadata = _build_metadata(doc, chunk)
            records.append(VectorRecord(id=chunk.id, text=text, metadata=metadata))

    return tuple(records)


def _build_text(title: str, chunk: Chunk) -> str:
    parts: list[str] = [title]
    if chunk.heading_path:
        parts.append(" > ".join(chunk.heading_path))
    parts.append(chunk.content_text)
    return "\n\n".join(parts)


def _build_metadata(doc: Document, chunk: Chunk) -> dict[str, object]:
    return {
        "document_id": str(doc.id),
        "source_uri": doc.source_uri,
        "section_id": str(chunk.section_id),
        "heading_path": list(chunk.heading_path),
        "lineage": list(chunk.lineage),
        "frontmatter": doc.frontmatter,
        "source_type": doc.source_type,
        "chunk_order_index": chunk.order_index,
        "section_chunk_index": chunk.section_chunk_index,
    }
