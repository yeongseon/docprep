"""Vector-ready export - build VectorRecords from Documents."""

from __future__ import annotations

from collections.abc import Iterator
import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
import importlib
import json
from typing import TextIO, cast
import uuid

from .ids import SCHEMA_VERSION, chunk_id, document_id
from .metadata import Metadata, normalize_metadata
from .models.domain import (
    Chunk,
    Document,
    RevisionDiff,
    TextPrependStrategy,
    VectorRecord,
    VectorRecordV1,
)


def build_vector_records(
    documents: tuple[Document, ...],
    *,
    text_prepend: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
) -> tuple[VectorRecord, ...]:
    return tuple(iter_vector_records(documents, text_prepend=text_prepend))


def build_vector_records_v1(
    documents: tuple[Document, ...],
    *,
    text_prepend: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
    created_at: str | None = None,
) -> tuple[VectorRecordV1, ...]:
    return tuple(
        iter_vector_records_v1(
            documents,
            text_prepend=text_prepend,
            created_at=created_at,
        )
    )


def iter_vector_records(
    documents: tuple[Document, ...],
    *,
    text_prepend: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
) -> Iterator[VectorRecord]:
    for doc in documents:
        for chunk in doc.chunks:
            text = _build_text(doc.title, chunk, text_prepend)
            metadata = _build_metadata(doc, chunk)
            yield VectorRecord(id=chunk.id, text=text, metadata=metadata)


def iter_vector_records_v1(
    documents: tuple[Document, ...],
    *,
    text_prepend: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
    created_at: str | None = None,
) -> Iterator[VectorRecordV1]:
    package_module = importlib.import_module("docprep")
    package_version = cast(str, getattr(package_module, "__version__"))

    timestamp = created_at or datetime.now(timezone.utc).isoformat()

    for doc in documents:
        user_meta = _merge_user_metadata(doc)
        section_anchor_by_id = {section.id: section.anchor for section in doc.sections}
        for chunk in doc.chunks:
            yield _build_vector_record_v1(
                doc,
                chunk,
                section_anchor_by_id=section_anchor_by_id,
                user_metadata=user_meta,
                pipeline_version=package_version,
                created_at=timestamp,
                text_prepend=text_prepend,
            )


def record_to_jsonl(record: VectorRecord | VectorRecordV1) -> str:
    data = dataclasses.asdict(record)
    for key in ("id", "document_id", "section_id"):
        if key in data and data[key] is not None:
            data[key] = str(data[key])
    return json.dumps(data, ensure_ascii=False, default=str)


def write_jsonl(
    records: Iterator[VectorRecord] | Iterator[VectorRecordV1],
    output: TextIO,
) -> int:
    count = 0
    for record in records:
        output.write(record_to_jsonl(record))
        output.write("\n")
        count += 1
    return count


@dataclass(frozen=True, slots=True)
class ExportDelta:
    added: tuple[VectorRecordV1, ...] = ()
    modified: tuple[VectorRecordV1, ...] = ()
    deleted_ids: tuple[uuid.UUID, ...] = ()


def build_export_delta(
    diff_results: tuple[RevisionDiff, ...],
    documents: tuple[Document, ...],
    *,
    text_prepend: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
    created_at: str | None = None,
) -> ExportDelta:
    package_module = importlib.import_module("docprep")
    package_version = cast(str, getattr(package_module, "__version__"))
    timestamp = created_at or datetime.now(timezone.utc).isoformat()

    docs_by_uri = {document.source_uri: document for document in documents}
    added: list[VectorRecordV1] = []
    modified: list[VectorRecordV1] = []
    deleted_ids: list[uuid.UUID] = []

    for diff in diff_results:
        doc = docs_by_uri.get(diff.source_uri)
        if doc is not None:
            user_meta = _merge_user_metadata(doc)
            section_anchor_by_id = {section.id: section.anchor for section in doc.sections}
            chunks_by_anchor = {chunk.anchor: chunk for chunk in doc.chunks}
        else:
            user_meta = {}
            section_anchor_by_id = {}
            chunks_by_anchor = {}

        for delta in diff.chunk_deltas:
            if delta.status == "added":
                chunk = chunks_by_anchor.get(delta.anchor)
                if chunk is None or doc is None:
                    continue
                added.append(
                    _build_vector_record_v1(
                        doc,
                        chunk,
                        section_anchor_by_id=section_anchor_by_id,
                        user_metadata=user_meta,
                        pipeline_version=package_version,
                        created_at=timestamp,
                        text_prepend=text_prepend,
                    )
                )
            elif delta.status == "modified":
                chunk = chunks_by_anchor.get(delta.anchor)
                if chunk is None or doc is None:
                    continue
                modified.append(
                    _build_vector_record_v1(
                        doc,
                        chunk,
                        section_anchor_by_id=section_anchor_by_id,
                        user_metadata=user_meta,
                        pipeline_version=package_version,
                        created_at=timestamp,
                        text_prepend=text_prepend,
                    )
                )
            elif delta.status == "removed":
                doc_id = document_id(diff.source_uri)
                deleted_ids.append(chunk_id(doc_id, delta.anchor))

    return ExportDelta(
        added=tuple(added),
        modified=tuple(modified),
        deleted_ids=tuple(deleted_ids),
    )


def _build_vector_record_v1(
    doc: Document,
    chunk: Chunk,
    *,
    section_anchor_by_id: dict[uuid.UUID, str],
    user_metadata: Metadata,
    pipeline_version: str,
    created_at: str,
    text_prepend: TextPrependStrategy,
) -> VectorRecordV1:
    text = _build_text(doc.title, chunk, text_prepend)
    return VectorRecordV1(
        id=chunk.id,
        document_id=doc.id,
        section_id=chunk.section_id,
        chunk_anchor=chunk.anchor,
        section_anchor=section_anchor_by_id.get(chunk.section_id, ""),
        text=text,
        content_hash=chunk.content_hash,
        char_count=len(chunk.content_text),
        source_uri=doc.source_uri,
        title=doc.title,
        section_path=chunk.heading_path,
        schema_version=SCHEMA_VERSION,
        pipeline_version=pipeline_version,
        created_at=created_at,
        user_metadata=user_metadata,
    )


def _build_text(
    title: str,
    chunk: Chunk,
    strategy: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
) -> str:
    parts: list[str] = []

    if strategy in (TextPrependStrategy.TITLE_ONLY, TextPrependStrategy.TITLE_AND_HEADING_PATH):
        parts.append(title)

    if strategy in (TextPrependStrategy.HEADING_PATH, TextPrependStrategy.TITLE_AND_HEADING_PATH):
        if chunk.heading_path:
            parts.append(" > ".join(chunk.heading_path))

    parts.append(chunk.content_text)
    return "\n\n".join(parts)


def _merge_user_metadata(doc: Document) -> Metadata:
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
    return {**normalized_source_meta, **normalized_fm}


def _build_metadata(doc: Document, chunk: Chunk) -> Metadata:
    user_metadata = _merge_user_metadata(doc)

    system_metadata: Metadata = {
        "docprep.document_id": str(doc.id),
        "docprep.source_uri": doc.source_uri,
        "docprep.source_type": doc.source_type,
        "docprep.section_id": str(chunk.section_id),
        "docprep.heading_path": list(chunk.heading_path),
        "docprep.lineage": list(chunk.lineage),
        "docprep.chunk_anchor": chunk.anchor,
        "docprep.chunk_order_index": chunk.order_index,
        "docprep.section_chunk_index": chunk.section_chunk_index,
        "docprep.schema_version": SCHEMA_VERSION,
    }

    return {**user_metadata, **system_metadata}
