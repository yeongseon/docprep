from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from docprep.exceptions import SinkError
from docprep.models.domain import Chunk, Document, Section
from docprep.sinks.orm import DocumentRow, row_to_domain
from docprep.sinks.sqlalchemy import SQLAlchemySink


def _document(*, checksum: str = "checksum", body: str = "Body") -> Document:
    doc_id = uuid.uuid4()
    section = Section(
        id=uuid.uuid4(),
        document_id=doc_id,
        order_index=0,
        heading="Intro",
        heading_level=1,
        heading_path=("Intro",),
        lineage=("root",),
        content_markdown=body,
    )
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        section_id=section.id,
        order_index=0,
        section_chunk_index=0,
        content_text=body,
        heading_path=("Intro",),
        lineage=("root",),
    )
    return Document(
        id=doc_id,
        source_uri="docs/example.md",
        title="Example",
        source_checksum=checksum,
        body_markdown=body,
        sections=(section,),
        chunks=(chunk,),
    )


def test_upsert_new_document_persists_correctly() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    document = _document()

    skipped = sink.upsert([document])

    assert skipped == ()
    with Session(engine) as session:
        row = session.execute(select(DocumentRow)).scalar_one()
        assert row_to_domain(row) == document


def test_upsert_existing_unchanged_document_returns_skipped_uri() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    document = _document()
    _ = sink.upsert([document])

    skipped = sink.upsert([document])

    assert skipped == (document.source_uri,)


def test_upsert_existing_changed_document_replaces_it() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    original = _document(checksum="old", body="Old")
    updated = _document(checksum="new", body="New")
    updated = Document(
        id=updated.id,
        source_uri=original.source_uri,
        title=updated.title,
        source_checksum=updated.source_checksum,
        body_markdown=updated.body_markdown,
        sections=updated.sections,
        chunks=updated.chunks,
    )
    _ = sink.upsert([original])

    _ = sink.upsert([updated])

    with Session(engine) as session:
        rows = session.execute(select(DocumentRow)).scalars().all()
        assert len(rows) == 1
        assert rows[0].source_checksum == "new"
        assert rows[0].body_markdown == "New"


def test_stats_returns_correct_counts() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    _ = sink.upsert([_document()])

    stats = sink.stats()

    assert stats.documents == 1
    assert stats.sections == 1
    assert stats.chunks == 1


def test_sink_error_is_raised_on_database_failure() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine, create_tables=False)

    with pytest.raises(SinkError, match="Failed to upsert documents"):
        _ = sink.upsert([_document()])
