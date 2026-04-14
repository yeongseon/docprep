from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Engine, create_engine, inspect, select, text, update
from sqlalchemy.orm import Session

from docprep.exceptions import MetadataError, SinkError
from docprep.ids import SCHEMA_VERSION
from docprep.models.domain import Chunk, Document, RunManifest, Section, SourceScope
from docprep.sinks.orm import DocprepMeta, DocumentRevisionRow, DocumentRow, row_to_domain
from docprep.sinks.sqlalchemy import SQLAlchemySink


def _document(
    *,
    checksum: str = "checksum",
    body: str = "Body",
    document_id: uuid.UUID | None = None,
) -> Document:
    doc_id = document_id or uuid.uuid4()
    section = Section(
        id=uuid.uuid4(),
        document_id=doc_id,
        order_index=0,
        heading="Intro",
        heading_level=1,
        anchor="intro",
        content_hash="sectionhash000001",
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
        anchor="intro:chunkhash000001",
        content_hash="chunkhash000001",
        content_text=body,
        char_start=0,
        char_end=len(body),
        token_count=len(body.split()),
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

    result = sink.upsert([document])

    assert result.skipped_source_uris == ()
    assert result.updated_source_uris == (document.source_uri,)
    with Session(engine) as session:
        row = session.execute(select(DocumentRow)).scalar_one()
        assert row_to_domain(row) == document
        revision_rows = session.execute(select(DocumentRevisionRow)).scalars().all()
        assert len(revision_rows) == 1
        assert revision_rows[0].revision_number == 1
        assert revision_rows[0].is_current is True


def test_upsert_existing_unchanged_document_returns_skipped_uri() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    document = _document()
    _ = sink.upsert([document])

    result = sink.upsert([document])

    assert result.skipped_source_uris == (document.source_uri,)
    assert result.updated_source_uris == ()
    with Session(engine) as session:
        revision_rows = session.execute(select(DocumentRevisionRow)).scalars().all()
        assert len(revision_rows) == 1


def test_upsert_existing_changed_document_replaces_it() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    original = _document(checksum="old", body="Old")
    updated = _document(checksum="new", body="New", document_id=original.id)
    _ = sink.upsert([original])

    result = sink.upsert([updated])

    assert result.skipped_source_uris == ()
    assert result.updated_source_uris == (original.source_uri,)

    with Session(engine) as session:
        rows = session.execute(select(DocumentRow)).scalars().all()
        assert len(rows) == 1
        assert rows[0].source_checksum == "new"
        assert rows[0].body_markdown == "New"
        revision_rows = (
            session.execute(
                select(DocumentRevisionRow).order_by(DocumentRevisionRow.revision_number)
            )
            .scalars()
            .all()
        )
        assert [row.revision_number for row in revision_rows] == [1, 2]
        assert revision_rows[0].is_current is False
        assert revision_rows[1].is_current is True


def test_upsert_same_checksum_different_identity_version_triggers_update() -> None:
    """When identity_version differs, unchanged docs are re-processed (not skipped)."""
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    # Create initial document with identity_version=3 (default)
    original = _document(checksum="same-checksum", body="Body")
    _ = sink.upsert([original])

    # Create updated document: same checksum + body, but different identity_version
    # Manually override identity_version to simulate a version bump scenario
    updated = Document(
        id=original.id,
        source_uri=original.source_uri,
        title=original.title,
        source_checksum=original.source_checksum,  # Same checksum
        identity_version=2,  # Different version
        source_type=original.source_type,
        frontmatter=original.frontmatter,
        source_metadata=original.source_metadata,
        body_markdown=original.body_markdown,  # Same body
        sections=original.sections,
        chunks=original.chunks,
    )

    # Upsert should treat this as updated, not skipped
    result = sink.upsert([updated])

    assert result.skipped_source_uris == ()
    assert result.updated_source_uris == (original.source_uri,)

    # Verify database state: identity_version should be updated
    with Session(engine) as session:
        row = session.execute(select(DocumentRow)).scalar_one()
        assert row.identity_version == 2
        # Verify revisions: should have 2 revisions now
        revision_rows = (
            session.execute(
                select(DocumentRevisionRow).order_by(DocumentRevisionRow.revision_number)
            )
            .scalars()
            .all()
        )
        assert len(revision_rows) == 2
        assert revision_rows[0].is_current is False
        assert revision_rows[1].is_current is True
        assert revision_rows[1].revision_number == 2


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


def test_upsert_raises_metadata_error_for_reserved_keys() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    doc = Document(
        id=uuid.uuid4(),
        source_uri="docs/bad.md",
        title="Bad",
        source_checksum="checksum",
        frontmatter={"docprep.source_uri": "smuggled"},
    )

    with pytest.raises(MetadataError, match="reserved prefix"):
        _ = sink.upsert([doc])


def _create_v0_schema(engine: Engine) -> None:
    statements = (
        """
        CREATE TABLE documents (
            id VARCHAR(36) PRIMARY KEY,
            source_uri VARCHAR(1024) NOT NULL,
            title VARCHAR(512) NOT NULL,
            source_checksum VARCHAR(64) NOT NULL,
            source_type VARCHAR(32) NOT NULL DEFAULT 'markdown',
            frontmatter JSON,
            source_metadata JSON,
            body_markdown TEXT NOT NULL DEFAULT ''
        )
        """,
        """
        CREATE TABLE sections (
            id VARCHAR(36) PRIMARY KEY,
            document_id VARCHAR(36) NOT NULL,
            order_index INTEGER NOT NULL,
            parent_id VARCHAR(36),
            heading VARCHAR(512),
            heading_level INTEGER NOT NULL DEFAULT 0,
            heading_path JSON,
            lineage JSON,
            content_markdown TEXT NOT NULL DEFAULT ''
        )
        """,
        """
        CREATE TABLE chunks (
            id VARCHAR(36) PRIMARY KEY,
            document_id VARCHAR(36) NOT NULL,
            section_id VARCHAR(36) NOT NULL,
            order_index INTEGER NOT NULL,
            section_chunk_index INTEGER NOT NULL,
            content_text TEXT NOT NULL,
            char_start INTEGER,
            char_end INTEGER,
            heading_path JSON,
            lineage JSON
        )
        """,
    )

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def test_fresh_database_stores_schema_version_on_init() -> None:
    engine = create_engine("sqlite://")
    _ = SQLAlchemySink(engine=engine)

    with Session(engine) as session:
        stored = session.execute(
            select(DocprepMeta.value).where(DocprepMeta.key == "schema_version")
        ).scalar_one()

    assert stored == str(SCHEMA_VERSION)


def test_reopening_database_with_matching_schema_version_succeeds() -> None:
    engine = create_engine("sqlite://")
    _ = SQLAlchemySink(engine=engine)

    reopened = SQLAlchemySink(engine=engine)

    with Session(engine) as session:
        stored = session.execute(
            select(DocprepMeta.value).where(DocprepMeta.key == "schema_version")
        ).scalar_one()

    assert isinstance(reopened, SQLAlchemySink)
    assert stored == str(SCHEMA_VERSION)


def test_reopening_database_with_mismatched_schema_version_raises() -> None:
    engine = create_engine("sqlite://")
    _ = SQLAlchemySink(engine=engine)

    with Session(engine) as session, session.begin():
        session.execute(
            update(DocprepMeta)
            .where(DocprepMeta.key == "schema_version")
            .values(value=str(SCHEMA_VERSION + 1))
        )

    with pytest.raises(
        SinkError,
        match=(
            rf"Database schema version {SCHEMA_VERSION + 1} does not match "
            rf"docprep schema version {SCHEMA_VERSION}\. "
            r"Run 'docprep migrate --db <url>' or recreate the database\."
        ),
    ):
        _ = SQLAlchemySink(engine=engine)


def test_migrate_from_v0_to_v1_adds_columns_and_schema_version() -> None:
    engine = create_engine("sqlite://")
    _create_v0_schema(engine)
    sink = SQLAlchemySink(engine=engine, create_tables=False)

    sink.migrate()

    inspector = inspect(engine)
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    section_columns = {column["name"] for column in inspector.get_columns("sections")}
    chunk_columns = {column["name"] for column in inspector.get_columns("chunks")}
    run_columns = {column["name"] for column in inspector.get_columns("ingestion_runs")}
    revision_columns = {column["name"] for column in inspector.get_columns("document_revisions")}

    with Session(engine) as session:
        stored = session.execute(
            select(DocprepMeta.value).where(DocprepMeta.key == "schema_version")
        ).scalar_one()

    assert "identity_version" in document_columns
    assert {"anchor", "content_hash"}.issubset(section_columns)
    assert {"anchor", "content_hash", "char_start", "char_end", "token_count"}.issubset(
        chunk_columns
    )
    assert {"id", "scope_prefixes", "scope_explicit", "source_uris_seen", "timestamp"}.issubset(
        run_columns
    )
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
    assert stored == str(SCHEMA_VERSION)


def test_migrate_is_idempotent() -> None:
    engine = create_engine("sqlite://")
    _create_v0_schema(engine)
    sink = SQLAlchemySink(engine=engine, create_tables=False)

    sink.migrate()
    sink.migrate()

    with Session(engine) as session:
        version_rows = (
            session.execute(select(DocprepMeta).where(DocprepMeta.key == "schema_version"))
            .scalars()
            .all()
        )

    assert len(version_rows) == 1
    assert version_rows[0].value == str(SCHEMA_VERSION)


def test_record_run_and_get_latest_run_round_trip() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    manifest = RunManifest(
        run_id=uuid.uuid4(),
        scope=SourceScope(prefixes=("file:docs/api/",), explicit=True),
        source_uris_seen=("file:docs/api/guide.md",),
        timestamp="2026-01-01T00:00:00+00:00",
    )

    sink.record_run(manifest)

    assert sink.get_latest_run() == manifest


def test_get_stored_uris_in_scope_filters_documents() -> None:
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)
    first = _document()
    second = Document(
        id=uuid.uuid4(),
        source_uri="docs/other.md",
        title="Other",
        source_checksum="checksum-other",
    )
    _ = sink.upsert([first, second])

    in_scope = sink.get_stored_uris_in_scope(SourceScope(prefixes=("docs/",)))

    assert in_scope == {"docs/example.md", "docs/other.md"}
