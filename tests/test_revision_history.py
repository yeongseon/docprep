from __future__ import annotations

import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from docprep.models.domain import Chunk, Document, Section
from docprep.sinks.orm import DocumentRevisionRow
from docprep.sinks.sqlalchemy import SQLAlchemySink


def _document(
    *,
    document_id: uuid.UUID,
    checksum: str,
    body: str,
    section_anchor: str,
    section_hash: str,
    chunk_anchor: str,
    chunk_hash: str,
) -> Document:
    section = Section(
        id=uuid.uuid4(),
        document_id=document_id,
        order_index=0,
        heading="Intro",
        heading_level=1,
        anchor=section_anchor,
        content_hash=section_hash,
        heading_path=("Intro",),
        lineage=("root",),
        content_markdown=body,
    )
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document_id,
        section_id=section.id,
        order_index=0,
        section_chunk_index=0,
        anchor=chunk_anchor,
        content_hash=chunk_hash,
        content_text=body,
        char_start=0,
        char_end=len(body),
        token_count=len(body.split()),
        heading_path=("Intro",),
        lineage=("root",),
    )
    return Document(
        id=document_id,
        source_uri="docs/example.md",
        title="Example",
        source_checksum=checksum,
        body_markdown=body,
        sections=(section,),
        chunks=(chunk,),
    )


def test_first_ingest_creates_current_revision_number_one() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    document_id = uuid.uuid4()
    run_id = uuid.uuid4()
    document = _document(
        document_id=document_id,
        checksum="checksum-1",
        body="Body one",
        section_anchor="intro",
        section_hash="sectionhash000001",
        chunk_anchor="intro:chunkhash000001",
        chunk_hash="chunkhash000001",
    )

    _ = sink.upsert([document], run_id=run_id)

    with Session(engine) as session:
        row = session.execute(select(DocumentRevisionRow)).scalar_one()
        assert row.document_id == str(document_id)
        assert row.revision_number == 1
        assert row.is_current is True
        assert row.ingestion_run_id == str(run_id)


def test_changed_document_creates_next_revision_and_marks_previous_not_current() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    document_id = uuid.uuid4()
    v1 = _document(
        document_id=document_id,
        checksum="checksum-1",
        body="Body one",
        section_anchor="intro",
        section_hash="sectionhash000001",
        chunk_anchor="intro:chunkhash000001",
        chunk_hash="chunkhash000001",
    )
    v2 = _document(
        document_id=document_id,
        checksum="checksum-2",
        body="Body two",
        section_anchor="overview",
        section_hash="sectionhash000002",
        chunk_anchor="overview:chunkhash000002",
        chunk_hash="chunkhash000002",
    )

    _ = sink.upsert([v1])
    _ = sink.upsert([v2])

    with Session(engine) as session:
        rows = (
            session.execute(
                select(DocumentRevisionRow).order_by(DocumentRevisionRow.revision_number)
            )
            .scalars()
            .all()
        )
        assert [row.revision_number for row in rows] == [1, 2]
        assert rows[0].is_current is False
        assert rows[1].is_current is True


def test_unchanged_document_is_skipped_without_creating_new_revision() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    document = _document(
        document_id=uuid.uuid4(),
        checksum="checksum-1",
        body="Body one",
        section_anchor="intro",
        section_hash="sectionhash000001",
        chunk_anchor="intro:chunkhash000001",
        chunk_hash="chunkhash000001",
    )

    _ = sink.upsert([document])
    result = sink.upsert([document])

    assert result.skipped_source_uris == ("docs/example.md",)
    with Session(engine) as session:
        rows = session.execute(select(DocumentRevisionRow)).scalars().all()
        assert len(rows) == 1


def test_current_and_previous_revisions_are_queryable() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    document_id = uuid.uuid4()
    revisions = [
        _document(
            document_id=document_id,
            checksum="checksum-1",
            body="Body one",
            section_anchor="intro",
            section_hash="sectionhash000001",
            chunk_anchor="intro:chunkhash000001",
            chunk_hash="chunkhash000001",
        ),
        _document(
            document_id=document_id,
            checksum="checksum-2",
            body="Body two",
            section_anchor="overview",
            section_hash="sectionhash000002",
            chunk_anchor="overview:chunkhash000002",
            chunk_hash="chunkhash000002",
        ),
    ]

    _ = sink.upsert([revisions[0]])
    _ = sink.upsert([revisions[1]])

    current = sink.get_current_revision(document_id)
    previous = sink.get_previous_revision(document_id)

    assert current is not None
    assert previous is not None
    assert current.revision_number == 2
    assert current.is_current is True
    assert previous.revision_number == 1
    assert previous.is_current is False


def test_get_revisions_returns_descending_revision_order_and_limit() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    document_id = uuid.uuid4()

    for idx in range(1, 4):
        _ = sink.upsert(
            [
                _document(
                    document_id=document_id,
                    checksum=f"checksum-{idx}",
                    body=f"Body {idx}",
                    section_anchor=f"section-{idx}",
                    section_hash=f"sectionhash{idx:06d}",
                    chunk_anchor=f"section-{idx}:chunkhash{idx:06d}",
                    chunk_hash=f"chunkhash{idx:06d}",
                )
            ]
        )

    revisions = sink.get_revisions(document_id)
    limited = sink.get_revisions(document_id, limit=2)

    assert [revision.revision_number for revision in revisions] == [3, 2, 1]
    assert [revision.revision_number for revision in limited] == [3, 2]


def test_prune_revisions_keeps_max_depth_per_document() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    document_id = uuid.uuid4()

    for idx in range(1, 6):
        _ = sink.upsert(
            [
                _document(
                    document_id=document_id,
                    checksum=f"checksum-{idx}",
                    body=f"Body {idx}",
                    section_anchor=f"section-{idx}",
                    section_hash=f"sectionhash{idx:06d}",
                    chunk_anchor=f"section-{idx}:chunkhash{idx:06d}",
                    chunk_hash=f"chunkhash{idx:06d}",
                )
            ]
        )

    deleted_count = sink.prune_revisions(max_depth=2)
    remaining = sink.get_revisions(document_id)

    assert deleted_count == 3
    assert [revision.revision_number for revision in remaining] == [5, 4]


def test_revision_snapshots_store_and_match_document_anchors_and_hashes() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    document_id = uuid.uuid4()
    document = _document(
        document_id=document_id,
        checksum="checksum-1",
        body="Body one",
        section_anchor="intro",
        section_hash="sectionhash000001",
        chunk_anchor="intro:chunkhash000001",
        chunk_hash="chunkhash000001",
    )

    _ = sink.upsert([document])

    revision = sink.get_current_revision(document_id)

    assert revision is not None
    assert revision.section_anchors == tuple(section.anchor for section in document.sections)
    assert revision.chunk_anchors == tuple(chunk.anchor for chunk in document.chunks)
    assert revision.section_hashes == tuple(section.content_hash for section in document.sections)
    assert revision.chunk_hashes == tuple(chunk.content_hash for chunk in document.chunks)
