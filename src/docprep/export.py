"""Vector-ready export — build VectorRecords from Documents."""

from __future__ import annotations

from docprep.metadata import Metadata, normalize_metadata
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


def _build_metadata(doc: Document, chunk: Chunk) -> Metadata:
    # Revalidate user metadata at export boundary
    normalized_source_meta = normalize_metadata(
        doc.source_metadata,
        source=doc.source_uri,
        field_name="source_metadata",
    )
    normalized_fm = normalize_metadata(
        doc.frontmatter,
        source=doc.source_uri,
        field_name="frontmatter",
    )

    # Merge: source_metadata first, frontmatter overrides on duplicate keys
    user_metadata: Metadata = {**normalized_source_meta, **normalized_fm}

    # System keys under reserved namespace
    system_metadata: Metadata = {
        "docprep.document_id": str(doc.id),
        "docprep.source_uri": doc.source_uri,
        "docprep.source_type": doc.source_type,
        "docprep.section_id": str(chunk.section_id),
        "docprep.heading_path": list(chunk.heading_path),
        "docprep.lineage": list(chunk.lineage),
        "docprep.chunk_order_index": chunk.order_index,
        "docprep.section_chunk_index": chunk.section_chunk_index,
    }

    return {**user_metadata, **system_metadata}
