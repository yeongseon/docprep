"""Domain dataclasses for the docprep pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
import uuid

from docprep.metadata import Metadata


@dataclass(frozen=True, kw_only=True, slots=True)
class Section:
    """A heading-delimited section within a document."""

    id: uuid.UUID
    document_id: uuid.UUID
    order_index: int
    parent_id: uuid.UUID | None = None
    heading: str | None = None
    heading_level: int = 0
    heading_path: tuple[str, ...] = ()
    lineage: tuple[str, ...] = ()
    content_markdown: str = ""


@dataclass(frozen=True, kw_only=True, slots=True)
class Chunk:
    """A sized text chunk derived from a section."""

    id: uuid.UUID
    document_id: uuid.UUID
    section_id: uuid.UUID
    order_index: int
    section_chunk_index: int
    content_text: str
    heading_path: tuple[str, ...] = ()
    lineage: tuple[str, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class Document:
    """A fully parsed and optionally chunked document."""

    id: uuid.UUID
    source_uri: str
    title: str
    source_checksum: str
    source_type: str = "markdown"
    frontmatter: Metadata = field(default_factory=dict)
    source_metadata: Metadata = field(default_factory=dict)
    body_markdown: str = ""
    sections: tuple[Section, ...] = ()
    chunks: tuple[Chunk, ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class VectorRecord:
    """A vector-ready record for embedding and retrieval."""

    id: uuid.UUID
    text: str
    metadata: Metadata = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True, slots=True)
class IngestResult:
    """Summary of an ingest pipeline run."""

    documents: tuple[Document, ...]
    skipped_source_uris: tuple[str, ...] = ()
    persisted: bool = False
    sink_name: str | None = None
