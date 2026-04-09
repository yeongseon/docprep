from __future__ import annotations

from datetime import date, datetime, timezone
from typing import cast
import uuid

import pytest
from sqlalchemy import create_engine, inspect

from docprep.exceptions import MetadataError
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


def test_domain_to_row_rejects_reserved_metadata_keys() -> None:
    document = Document(
        id=_document().id,
        source_uri="docs/example.md",
        title="Example",
        source_checksum="checksum",
        frontmatter={"docprep.source_uri": "bad"},
    )

    with pytest.raises(MetadataError, match=r"frontmatter\.docprep\.source_uri"):
        _ = domain_to_row(document)


def test_row_to_domain_normalizes_metadata_on_read() -> None:
    row = domain_to_row(_document())
    row.frontmatter = {
        "published": date(2024, 1, 15),
        "published_at": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    }
    row.source_metadata = {"lang": "en"}

    domain = cast(Document, row_to_domain(row))

    assert domain.frontmatter == {
        "published": "2024-01-15",
        "published_at": "2024-01-15T10:30:00+00:00",
    }
    assert domain.source_metadata == {"lang": "en"}


def test_row_to_domain_rejects_reserved_keys_in_stored_metadata() -> None:
    row = domain_to_row(_document())
    row.source_metadata = {"docprep.imported_at": "2024-01-15"}

    with pytest.raises(MetadataError, match="reserved prefix"):
        _ = row_to_domain(row)


def test_domain_to_row_rejects_non_document_input() -> None:
    with pytest.raises(TypeError, match="Expected Document"):
        _ = domain_to_row("not-a-document")


def test_domain_to_row_normalizes_metadata_values() -> None:
    doc = Document(
        id=uuid.uuid4(),
        source_uri="docs/example.md",
        title="Example",
        source_checksum="checksum",
        frontmatter={"tags": ("python", "docs")},
        source_metadata={"lang": "en"},
    )

    row = domain_to_row(doc)

    assert row.frontmatter == {"tags": ["python", "docs"]}
    assert row.source_metadata == {"lang": "en"}


def test_tables_are_created_correctly() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) == {"chunks", "documents", "sections"}
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    assert {"id", "source_uri", "title", "source_checksum"}.issubset(document_columns)
