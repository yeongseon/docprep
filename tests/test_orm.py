from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, inspect

from docprep.models.domain import Chunk, Document, Section
from docprep.sinks.orm import Base, domain_to_row, row_to_domain


def _document() -> Document:
    doc_id = uuid.uuid4()
    section = Section(
        id=uuid.uuid4(),
        document_id=doc_id,
        order_index=0,
        heading="Intro",
        heading_level=1,
        heading_path=("Intro",),
        lineage=("lineage",),
        content_markdown="Body",
    )
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        section_id=section.id,
        order_index=0,
        section_chunk_index=0,
        content_text="Body",
        heading_path=("Intro",),
        lineage=("lineage",),
    )
    return Document(
        id=doc_id,
        source_uri="docs/example.md",
        title="Example",
        source_checksum="checksum",
        frontmatter={"author": "Ada"},
        source_metadata={"lang": "en"},
        body_markdown="# Intro\nBody",
        sections=(section,),
        chunks=(chunk,),
    )


def test_domain_to_row_converts_document_correctly() -> None:
    row = domain_to_row(_document())

    assert row.source_uri == "docs/example.md"
    assert row.sections[0].heading == "Intro"
    assert row.chunks[0].content_text == "Body"


def test_row_to_domain_converts_document_row_correctly() -> None:
    domain = row_to_domain(domain_to_row(_document()))

    assert isinstance(domain, Document)
    assert domain.frontmatter == {"author": "Ada"}
    assert domain.sections[0].heading_path == ("Intro",)


def test_round_trip_conversion_preserves_data() -> None:
    document = _document()

    assert row_to_domain(domain_to_row(document)) == document


def test_domain_to_row_rejects_non_document_input() -> None:
    with pytest.raises(TypeError, match="Expected Document"):
        _ = domain_to_row("not-a-document")


def test_tables_are_created_correctly() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == {"chunks", "documents", "sections"}
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    assert {"id", "source_uri", "title", "source_checksum"}.issubset(document_columns)
