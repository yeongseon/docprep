from __future__ import annotations

from datetime import date, datetime, timezone
from typing import cast
import uuid

import pytest
from sqlalchemy import create_engine, inspect

from docprep.exceptions import MetadataError
from docprep.models.domain import (
    Chunk,
    Document,
    DocumentRevision,
    RunManifest,
    Section,
    SourceScope,
)
from docprep.sinks.orm import (
    Base,
    DocumentRevisionRow,
    domain_to_row,
    revision_from_document,
    row_to_domain,
    row_to_revision,
    row_to_run_manifest,
    run_manifest_to_row,
)


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
        char_start=0,
        char_end=4,
        token_count=1,
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

    assert set(inspector.get_table_names()) == {
        "chunks",
        "document_revisions",
        "documents",
        "docprep_meta",
        "ingestion_runs",
        "sections",
    }
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    revision_columns = {column["name"] for column in inspector.get_columns("document_revisions")}
    section_columns = {column["name"] for column in inspector.get_columns("sections")}
    chunk_columns = {column["name"] for column in inspector.get_columns("chunks")}

    assert {
        "id",
        "document_id",
        "source_uri",
        "source_checksum",
        "revision_number",
        "ingestion_run_id",
        "section_anchors",
        "chunk_anchors",
        "section_hashes",
        "chunk_hashes",
        "is_current",
        "timestamp",
    }.issubset(revision_columns)
    assert {
        "id",
        "source_uri",
        "title",
        "source_checksum",
        "identity_version",
    }.issubset(document_columns)
    assert {"anchor", "content_hash"}.issubset(section_columns)
    assert {"anchor", "content_hash", "char_start", "char_end", "token_count"}.issubset(
        chunk_columns
    )


def test_run_manifest_row_round_trip() -> None:
    manifest = RunManifest(
        run_id=uuid.uuid4(),
        scope=SourceScope(prefixes=("file:docs/api/",), explicit=True),
        source_uris_seen=("file:docs/api/guide.md",),
        timestamp="2026-01-01T00:00:00+00:00",
    )

    row = run_manifest_to_row(manifest)
    converted = row_to_run_manifest(row)

    assert converted == manifest


def test_revision_from_document_and_row_round_trip() -> None:
    document = _document()
    run_id = uuid.uuid4()

    row = revision_from_document(
        document,
        revision_number=1,
        run_id=run_id,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    converted = row_to_revision(row)

    assert isinstance(converted, DocumentRevision)
    assert isinstance(row, DocumentRevisionRow)
    assert converted.document_id == document.id
    assert converted.source_uri == document.source_uri
    assert converted.source_checksum == document.source_checksum
    assert converted.revision_number == 1
    assert converted.ingestion_run_id == run_id
    assert converted.timestamp == "2026-01-01T00:00:00+00:00"
