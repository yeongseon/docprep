from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from typing import TypeAlias
import uuid

import pytest

from docprep.metadata import Metadata
from docprep.models.domain import (
    Chunk,
    Document,
    DocumentError,
    DocumentRevision,
    ErrorMode,
    IngestResult,
    IngestStageReport,
    PipelineStage,
    RunManifest,
    Section,
    SinkUpsertResult,
    SourceScope,
    StructuralAnnotation,
    StructureKind,
    TextPrependStrategy,
    VectorRecord,
    VectorRecordV1,
)
from docprep.progress import IngestProgressEvent

DomainDataclass: TypeAlias = (
    type[Section]
    | type[Chunk]
    | type[DocumentError]
    | type[Document]
    | type[DocumentRevision]
    | type[VectorRecord]
    | type[VectorRecordV1]
    | type[SinkUpsertResult]
    | type[SourceScope]
    | type[RunManifest]
    | type[IngestStageReport]
    | type[IngestResult]
    | type[StructuralAnnotation]
)


def _make_document() -> Document:
    return Document(
        id=uuid.uuid4(),
        source_uri="docs/example.md",
        title="Example",
        source_checksum="abc123",
    )


@pytest.mark.parametrize(
    "cls",
    [
        Section,
        Chunk,
        DocumentError,
        Document,
        DocumentRevision,
        VectorRecord,
        VectorRecordV1,
        SinkUpsertResult,
        SourceScope,
        RunManifest,
        IngestStageReport,
        IngestResult,
        StructuralAnnotation,
    ],
)
def test_all_domain_dataclasses_use_kw_only(cls: DomainDataclass) -> None:
    assert all(field.kw_only for field in fields(cls))


@pytest.mark.parametrize(
    ("instance", "attribute", "value"),
    [
        (
            Section(id=uuid.uuid4(), document_id=uuid.uuid4(), order_index=0),
            "heading",
            "new",
        ),
        (
            Chunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                section_id=uuid.uuid4(),
                order_index=0,
                section_chunk_index=0,
                content_text="body",
            ),
            "content_text",
            "new",
        ),
        (
            DocumentError(
                source_uri="docs/example.md",
                stage=PipelineStage.PARSE,
                error_type="RuntimeError",
                message="boom",
            ),
            "message",
            "updated",
        ),
        (_make_document(), "title", "Updated"),
        (
            DocumentRevision(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                source_uri="docs/example.md",
                source_checksum="checksum",
                revision_number=1,
            ),
            "revision_number",
            2,
        ),
        (VectorRecord(id=uuid.uuid4(), text="body"), "text", "Updated"),
        (
            VectorRecordV1(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                section_id=uuid.uuid4(),
                chunk_anchor="chunk",
                section_anchor="section",
                text="body",
                content_hash="hash",
                char_count=4,
                source_uri="docs/example.md",
                title="Example",
                section_path=("Intro",),
                schema_version=1,
                pipeline_version="0.0.1",
                created_at="2026-01-01T00:00:00+00:00",
            ),
            "text",
            "Updated",
        ),
        (SinkUpsertResult(), "skipped_source_uris", ("docs/example.md",)),
        (SourceScope(prefixes=("file:docs/",)), "explicit", True),
        (
            RunManifest(
                run_id=uuid.uuid4(),
                scope=SourceScope(prefixes=("file:docs/",)),
                source_uris_seen=("file:docs/guide.md",),
                timestamp="2026-01-01T00:00:00+00:00",
            ),
            "timestamp",
            "2026-01-02T00:00:00+00:00",
        ),
        (IngestStageReport(stage=PipelineStage.RUN, elapsed_ms=1.0), "elapsed_ms", 2.0),
        (IngestResult(documents=()), "persisted", True),
        (
            StructuralAnnotation(kind=StructureKind.TABLE, char_start=1, char_end=2),
            "char_end",
            3,
        ),
    ],
)
def test_all_domain_dataclasses_are_frozen(instance: object, attribute: str, value: object) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(instance, attribute, value)


@pytest.mark.parametrize(
    "cls",
    [
        Section,
        Chunk,
        DocumentError,
        Document,
        DocumentRevision,
        VectorRecord,
        VectorRecordV1,
        SinkUpsertResult,
        SourceScope,
        RunManifest,
        IngestStageReport,
        IngestResult,
        StructuralAnnotation,
    ],
)
def test_all_domain_dataclasses_use_slots(cls: DomainDataclass) -> None:
    assert hasattr(cls, "__slots__")


def test_document_default_values_work() -> None:
    document = _make_document()

    assert document.source_type == "markdown"
    assert document.frontmatter == {}
    assert document.source_metadata == {}
    assert document.body_markdown == ""
    assert document.structural_annotations == ()
    assert document.sections == ()
    assert document.chunks == ()


def test_can_create_all_domain_objects_with_required_fields() -> None:
    document_id = uuid.uuid4()
    section = Section(id=uuid.uuid4(), document_id=document_id, order_index=0)
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document_id,
        section_id=section.id,
        order_index=0,
        section_chunk_index=0,
        content_text="content",
    )
    document = Document(
        id=document_id,
        source_uri="docs/example.md",
        title="Example",
        source_checksum="checksum",
    )
    document_error = DocumentError(
        source_uri="docs/example.md",
        stage=PipelineStage.PARSE,
        error_type="RuntimeError",
        message="boom",
    )
    record = VectorRecord(id=uuid.uuid4(), text="vector text")
    revision = DocumentRevision(
        id=uuid.uuid4(),
        document_id=document_id,
        source_uri="docs/example.md",
        source_checksum="checksum",
        revision_number=1,
    )
    record_v1 = VectorRecordV1(
        id=uuid.uuid4(),
        document_id=document_id,
        section_id=section.id,
        chunk_anchor="intro:hash",
        section_anchor="intro",
        text="vector text",
        content_hash="hash",
        char_count=11,
        source_uri="docs/example.md",
        title="Example",
        section_path=("Intro",),
        schema_version=1,
        pipeline_version="0.0.1",
        created_at="2026-01-01T00:00:00+00:00",
    )
    sink_result = SinkUpsertResult()
    stage_report = IngestStageReport(stage=PipelineStage.RUN, elapsed_ms=1.0)
    result = IngestResult(documents=(document,), stage_reports=(stage_report,))

    assert section.document_id == document_id
    assert chunk.section_id == section.id
    assert chunk.structure_types == ()
    assert document_error.source_uri == "docs/example.md"
    assert document.title == "Example"
    assert revision.document_id == document_id
    assert record.metadata == {}
    assert record_v1.user_metadata == {}
    assert sink_result.updated_source_uris == ()
    assert stage_report.input_count == 0
    assert result.documents == (document,)
    assert result.stage_reports == (stage_report,)


def test_ingest_stage_report_default_values_work() -> None:
    report = IngestStageReport(stage=PipelineStage.PARSE, elapsed_ms=12.5)

    assert report.input_count == 0
    assert report.output_count == 0
    assert report.failed_count == 0


def test_sink_upsert_result_default_values_work() -> None:
    result = SinkUpsertResult()

    assert result.skipped_source_uris == ()
    assert result.updated_source_uris == ()
    assert result.deleted_source_uris == ()


def test_ingest_result_expanded_default_values_work() -> None:
    result = IngestResult(documents=())

    assert result.processed_count == 0
    assert result.skipped_count == 0
    assert result.updated_count == 0
    assert result.deleted_count == 0
    assert result.failed_count == 0
    assert result.skipped_source_uris == ()
    assert result.updated_source_uris == ()
    assert result.deleted_source_uris == ()
    assert result.failed_source_uris == ()
    assert result.errors == ()
    assert result.stage_reports == ()
    assert result.persisted is False
    assert result.sink_name is None
    assert result.run_manifest is None


def test_metadata_fields_use_metadata_type_alias() -> None:
    assert Document.__annotations__["frontmatter"] == "Metadata"
    assert Document.__annotations__["source_metadata"] == "Metadata"
    assert VectorRecord.__annotations__["metadata"] == "Metadata"
    assert VectorRecordV1.__annotations__["user_metadata"] == "Metadata"
    assert Metadata is not None


def test_section_and_chunk_schema_snapshot() -> None:
    section_schema = [field.name for field in fields(Section)]
    chunk_schema = [field.name for field in fields(Chunk)]

    assert section_schema == [
        "id",
        "document_id",
        "order_index",
        "parent_id",
        "heading",
        "heading_level",
        "anchor",
        "content_hash",
        "heading_path",
        "lineage",
        "content_markdown",
    ]
    assert chunk_schema == [
        "id",
        "document_id",
        "section_id",
        "order_index",
        "section_chunk_index",
        "anchor",
        "content_hash",
        "content_text",
        "char_start",
        "char_end",
        "token_count",
        "heading_path",
        "lineage",
        "structure_types",
    ]


def test_stage_schema_snapshot() -> None:
    stage_report_schema = [(field.name, field.type) for field in fields(IngestStageReport)]
    progress_event_schema = [(field.name, field.type) for field in fields(IngestProgressEvent)]

    assert stage_report_schema == [
        ("stage", "PipelineStage"),
        ("elapsed_ms", "float"),
        ("input_count", "int"),
        ("output_count", "int"),
        ("failed_count", "int"),
    ]
    assert progress_event_schema == [
        ("stage", "PipelineStage"),
        (
            "event",
            "Literal['started', 'completed', 'failed', 'skipped', 'updated']",
        ),
        ("source_uri", "str | None"),
        ("current", "int | None"),
        ("total", "int | None"),
        ("elapsed_ms", "float | None"),
        ("sections_count", "int | None"),
        ("chunks_count", "int | None"),
        ("sink_name", "str | None"),
        ("error_type", "str | None"),
    ]
    assert list(PipelineStage) == [
        PipelineStage.LOAD,
        PipelineStage.PARSE,
        PipelineStage.CHUNK,
        PipelineStage.PERSIST,
        PipelineStage.RUN,
    ]
    assert list(ErrorMode) == [
        ErrorMode.FAIL_FAST,
        ErrorMode.CONTINUE_ON_ERROR,
    ]


def test_scope_and_manifest_schema_snapshot() -> None:
    source_scope_schema = [field.name for field in fields(SourceScope)]
    run_manifest_schema = [field.name for field in fields(RunManifest)]

    assert source_scope_schema == ["prefixes", "explicit"]
    assert run_manifest_schema == ["run_id", "scope", "source_uris_seen", "timestamp"]


def test_document_revision_schema_snapshot() -> None:
    revision_schema = [field.name for field in fields(DocumentRevision)]

    assert revision_schema == [
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
    ]


def test_vector_record_v1_and_text_strategy_schema_snapshot() -> None:
    vector_record_v1_schema = [field.name for field in fields(VectorRecordV1)]

    assert vector_record_v1_schema == [
        "id",
        "document_id",
        "section_id",
        "chunk_anchor",
        "section_anchor",
        "text",
        "content_hash",
        "char_count",
        "source_uri",
        "title",
        "section_path",
        "schema_version",
        "pipeline_version",
        "created_at",
        "user_metadata",
    ]
    assert list(TextPrependStrategy) == [
        TextPrependStrategy.NONE,
        TextPrependStrategy.TITLE_ONLY,
        TextPrependStrategy.HEADING_PATH,
        TextPrependStrategy.TITLE_AND_HEADING_PATH,
    ]
