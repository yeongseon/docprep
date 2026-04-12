"""SQLAlchemy ORM models for persisting docprep data."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from ..models.domain import RunManifest, SourceScope


class Base(DeclarativeBase):
    pass


class DocprepMeta(Base):
    __tablename__ = "docprep_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False)


class IngestionRunRow(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    scope_prefixes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    scope_explicit: Mapped[bool] = mapped_column(nullable=False, default=False)
    source_uris_seen: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[str] = mapped_column(String(32), nullable=False)


class DocumentRevisionRow(Base):
    __tablename__ = "document_revisions"
    __table_args__ = (
        Index("ix_revisions_document_id", "document_id"),
        Index("ix_revisions_timestamp", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    revision_number: Mapped[int] = mapped_column(nullable=False)
    ingestion_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    section_anchors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    chunk_anchors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    section_hashes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    chunk_hashes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_current: Mapped[bool] = mapped_column(nullable=False, default=True)
    timestamp: Mapped[str] = mapped_column(String(32), nullable=False)


class DocumentRow(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("source_uri", name="uq_documents_source_uri"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="markdown")
    frontmatter: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    source_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    identity_version: Mapped[int] = mapped_column(nullable=False, default=2)

    sections: Mapped[list[SectionRow]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )
    chunks: Mapped[list[ChunkRow]] = relationship(
        back_populates="document", cascade="all, delete-orphan", passive_deletes=True
    )


class SectionRow(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("document_id", "order_index", name="uq_sections_doc_order"),
        Index("ix_sections_document_id", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    heading: Mapped[str | None] = mapped_column(String(512), nullable=True)
    heading_level: Mapped[int] = mapped_column(nullable=False, default=0)
    anchor: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    heading_path: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    lineage: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")

    document: Mapped[DocumentRow] = relationship(back_populates="sections")


class ChunkRow(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "section_id",
            "section_chunk_index",
            name="uq_chunks_doc_section_idx",
        ),
        Index("ix_chunks_document_id", "document_id"),
        Index("ix_chunks_section_id", "section_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(nullable=False)
    section_chunk_index: Mapped[int] = mapped_column(nullable=False)
    anchor: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading_path: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    lineage: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    document: Mapped[DocumentRow] = relationship(back_populates="chunks")
    section: Mapped[SectionRow] = relationship()


def domain_to_row(doc: object) -> DocumentRow:
    """Convert a domain Document to ORM rows (DocumentRow with nested children)."""
    from ..ids import IDENTITY_VERSION
    from ..metadata import normalize_metadata
    from ..models.domain import Document

    if not isinstance(doc, Document):
        raise TypeError(f"Expected Document, got {type(doc).__name__}")

    normalized_fm = normalize_metadata(
        doc.frontmatter, source=doc.source_uri, field_name="frontmatter"
    )
    normalized_sm = normalize_metadata(
        doc.source_metadata, source=doc.source_uri, field_name="source_metadata"
    )

    doc_row = DocumentRow(
        id=str(doc.id),
        source_uri=doc.source_uri,
        title=doc.title,
        source_checksum=doc.source_checksum,
        source_type=doc.source_type,
        frontmatter=normalized_fm or None,
        source_metadata=normalized_sm or None,
        body_markdown=doc.body_markdown,
        identity_version=IDENTITY_VERSION,
        sections=[
            SectionRow(
                id=str(s.id),
                document_id=str(doc.id),
                order_index=s.order_index,
                parent_id=str(s.parent_id) if s.parent_id else None,
                heading=s.heading,
                heading_level=s.heading_level,
                anchor=s.anchor,
                content_hash=s.content_hash,
                heading_path=list(s.heading_path) if s.heading_path else None,
                lineage=list(s.lineage) if s.lineage else None,
                content_markdown=s.content_markdown,
            )
            for s in doc.sections
        ],
        chunks=[
            ChunkRow(
                id=str(c.id),
                document_id=str(doc.id),
                section_id=str(c.section_id),
                order_index=c.order_index,
                section_chunk_index=c.section_chunk_index,
                anchor=c.anchor,
                content_hash=c.content_hash,
                content_text=c.content_text,
                char_start=c.char_start,
                char_end=c.char_end,
                token_count=c.token_count,
                heading_path=list(c.heading_path) if c.heading_path else None,
                lineage=list(c.lineage) if c.lineage else None,
            )
            for c in doc.chunks
        ],
    )
    return doc_row


def row_to_domain(row: DocumentRow) -> object:
    """Convert an ORM DocumentRow back to a domain Document."""
    from ..metadata import normalize_metadata
    from ..models.domain import Chunk, Document, Section

    fm = normalize_metadata(
        dict(row.frontmatter) if row.frontmatter else None,
        source=row.source_uri,
        field_name="frontmatter",
    )
    source_meta = normalize_metadata(
        dict(row.source_metadata) if row.source_metadata else None,
        source=row.source_uri,
        field_name="source_metadata",
    )

    sections = tuple(
        Section(
            id=uuid.UUID(s.id),
            document_id=uuid.UUID(s.document_id),
            order_index=s.order_index,
            parent_id=uuid.UUID(s.parent_id) if s.parent_id else None,
            heading=s.heading,
            heading_level=s.heading_level,
            anchor=s.anchor,
            content_hash=s.content_hash,
            heading_path=tuple(s.heading_path) if s.heading_path else (),
            lineage=tuple(s.lineage) if s.lineage else (),
            content_markdown=s.content_markdown,
        )
        for s in row.sections
    )

    chunks = tuple(
        Chunk(
            id=uuid.UUID(c.id),
            document_id=uuid.UUID(c.document_id),
            section_id=uuid.UUID(c.section_id),
            order_index=c.order_index,
            section_chunk_index=c.section_chunk_index,
            anchor=c.anchor,
            content_hash=c.content_hash,
            content_text=c.content_text,
            char_start=c.char_start or 0,
            char_end=c.char_end or 0,
            token_count=c.token_count,
            heading_path=tuple(c.heading_path) if c.heading_path else (),
            lineage=tuple(c.lineage) if c.lineage else (),
        )
        for c in row.chunks
    )

    return Document(
        id=uuid.UUID(row.id),
        source_uri=row.source_uri,
        title=row.title,
        source_checksum=row.source_checksum,
        source_type=row.source_type,
        frontmatter=fm,
        source_metadata=source_meta,
        body_markdown=row.body_markdown,
        sections=sections,
        chunks=chunks,
    )


def row_to_section(row: SectionRow) -> object:
    """Convert a SectionRow to a domain Section."""
    from ..models.domain import Section

    return Section(
        id=uuid.UUID(row.id),
        document_id=uuid.UUID(row.document_id),
        order_index=row.order_index,
        parent_id=uuid.UUID(row.parent_id) if row.parent_id else None,
        heading=row.heading,
        heading_level=row.heading_level,
        anchor=row.anchor,
        content_hash=row.content_hash,
        heading_path=tuple(row.heading_path) if row.heading_path else (),
        lineage=tuple(row.lineage) if row.lineage else (),
        content_markdown=row.content_markdown,
    )


def row_to_chunk(row: ChunkRow) -> object:
    """Convert a ChunkRow to a domain Chunk."""
    from ..models.domain import Chunk

    return Chunk(
        id=uuid.UUID(row.id),
        document_id=uuid.UUID(row.document_id),
        section_id=uuid.UUID(row.section_id),
        order_index=row.order_index,
        section_chunk_index=row.section_chunk_index,
        anchor=row.anchor,
        content_hash=row.content_hash,
        content_text=row.content_text,
        char_start=row.char_start or 0,
        char_end=row.char_end or 0,
        token_count=row.token_count,
        heading_path=tuple(row.heading_path) if row.heading_path else (),
        lineage=tuple(row.lineage) if row.lineage else (),
    )


def row_to_document_summary(row: DocumentRow) -> object:
    """Convert a DocumentRow to a lightweight Document WITHOUT sections/chunks."""
    from ..metadata import normalize_metadata
    from ..models.domain import Document

    fm = normalize_metadata(
        dict(row.frontmatter) if row.frontmatter else None,
        source=row.source_uri,
        field_name="frontmatter",
    )
    source_meta = normalize_metadata(
        dict(row.source_metadata) if row.source_metadata else None,
        source=row.source_uri,
        field_name="source_metadata",
    )
    return Document(
        id=uuid.UUID(row.id),
        source_uri=row.source_uri,
        title=row.title,
        source_checksum=row.source_checksum,
        source_type=row.source_type,
        frontmatter=fm,
        source_metadata=source_meta,
        body_markdown=row.body_markdown,
        sections=(),
        chunks=(),
    )


def revision_from_document(
    doc: object,
    revision_number: int,
    run_id: uuid.UUID | None,
    timestamp: str,
) -> DocumentRevisionRow:
    from ..models.domain import Document

    if not isinstance(doc, Document):
        raise TypeError(f"Expected Document, got {type(doc).__name__}")

    return DocumentRevisionRow(
        id=str(uuid.uuid4()),
        document_id=str(doc.id),
        source_uri=doc.source_uri,
        source_checksum=doc.source_checksum,
        revision_number=revision_number,
        ingestion_run_id=str(run_id) if run_id is not None else None,
        section_anchors=[section.anchor for section in doc.sections] or None,
        chunk_anchors=[chunk.anchor for chunk in doc.chunks] or None,
        section_hashes=[section.content_hash for section in doc.sections] or None,
        chunk_hashes=[chunk.content_hash for chunk in doc.chunks] or None,
        is_current=True,
        timestamp=timestamp,
    )


def row_to_revision(row: DocumentRevisionRow) -> object:
    from ..models.domain import DocumentRevision

    return DocumentRevision(
        id=uuid.UUID(row.id),
        document_id=uuid.UUID(row.document_id),
        source_uri=row.source_uri,
        source_checksum=row.source_checksum,
        revision_number=row.revision_number,
        ingestion_run_id=uuid.UUID(row.ingestion_run_id) if row.ingestion_run_id else None,
        section_anchors=tuple(row.section_anchors) if row.section_anchors else (),
        chunk_anchors=tuple(row.chunk_anchors) if row.chunk_anchors else (),
        section_hashes=tuple(row.section_hashes) if row.section_hashes else (),
        chunk_hashes=tuple(row.chunk_hashes) if row.chunk_hashes else (),
        is_current=row.is_current,
        timestamp=row.timestamp,
    )


def run_manifest_to_row(manifest: RunManifest) -> IngestionRunRow:
    return IngestionRunRow(
        id=str(manifest.run_id),
        scope_prefixes=list(manifest.scope.prefixes) if manifest.scope.prefixes else None,
        scope_explicit=manifest.scope.explicit,
        source_uris_seen=list(manifest.source_uris_seen) if manifest.source_uris_seen else None,
        timestamp=manifest.timestamp,
    )


def row_to_run_manifest(row: IngestionRunRow) -> RunManifest:
    timestamp = row.timestamp
    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1] + "+00:00"
    normalized_timestamp = datetime.fromisoformat(timestamp).astimezone(timezone.utc).isoformat()

    return RunManifest(
        run_id=uuid.UUID(row.id),
        scope=SourceScope(
            prefixes=tuple(row.scope_prefixes) if row.scope_prefixes else (),
            explicit=row.scope_explicit,
        ),
        source_uris_seen=tuple(row.source_uris_seen) if row.source_uris_seen else (),
        timestamp=normalized_timestamp,
    )
