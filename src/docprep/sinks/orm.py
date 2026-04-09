"""SQLAlchemy ORM models for persisting docprep data."""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


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
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    heading_path: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    lineage: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    document: Mapped[DocumentRow] = relationship(back_populates="chunks")
    section: Mapped[SectionRow] = relationship()


def domain_to_row(doc: object) -> DocumentRow:
    """Convert a domain Document to ORM rows (DocumentRow with nested children)."""
    from docprep.models.domain import Document

    if not isinstance(doc, Document):
        raise TypeError(f"Expected Document, got {type(doc).__name__}")

    doc_row = DocumentRow(
        id=str(doc.id),
        source_uri=doc.source_uri,
        title=doc.title,
        source_checksum=doc.source_checksum,
        source_type=doc.source_type,
        frontmatter=doc.frontmatter or None,
        source_metadata=doc.source_metadata or None,
        body_markdown=doc.body_markdown,
        sections=[
            SectionRow(
                id=str(s.id),
                document_id=str(doc.id),
                order_index=s.order_index,
                parent_id=str(s.parent_id) if s.parent_id else None,
                heading=s.heading,
                heading_level=s.heading_level,
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
                content_text=c.content_text,
                heading_path=list(c.heading_path) if c.heading_path else None,
                lineage=list(c.lineage) if c.lineage else None,
            )
            for c in doc.chunks
        ],
    )
    return doc_row


def row_to_domain(row: DocumentRow) -> object:
    """Convert an ORM DocumentRow back to a domain Document."""
    from docprep.models.domain import Chunk, Document, Section

    sections = tuple(
        Section(
            id=uuid.UUID(s.id),
            document_id=uuid.UUID(s.document_id),
            order_index=s.order_index,
            parent_id=uuid.UUID(s.parent_id) if s.parent_id else None,
            heading=s.heading,
            heading_level=s.heading_level,
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
            content_text=c.content_text,
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
        frontmatter=dict(row.frontmatter) if row.frontmatter else {},
        source_metadata=dict(row.source_metadata) if row.source_metadata else {},
        body_markdown=row.body_markdown,
        sections=sections,
        chunks=chunks,
    )
