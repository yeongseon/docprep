from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from typing import TypeAlias
import uuid

import pytest

from docprep.metadata import Metadata
from docprep.models.domain import (
    Chunk,
    Document,
    IngestResult,
    IngestStageReport,
    Section,
    SinkUpsertResult,
    VectorRecord,
)

DomainDataclass: TypeAlias = (
    type[Section]
    | type[Chunk]
    | type[Document]
    | type[VectorRecord]
    | type[SinkUpsertResult]
    | type[IngestStageReport]
    | type[IngestResult]
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
    [Section, Chunk, Document, VectorRecord, SinkUpsertResult, IngestStageReport, IngestResult],
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
        (_make_document(), "title", "Updated"),
        (VectorRecord(id=uuid.uuid4(), text="body"), "text", "Updated"),
        (SinkUpsertResult(), "skipped_source_uris", ("docs/example.md",)),
        (IngestStageReport(stage="run", elapsed_ms=1.0), "elapsed_ms", 2.0),
        (IngestResult(documents=()), "persisted", True),
    ],
)
def test_all_domain_dataclasses_are_frozen(instance: object, attribute: str, value: object) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(instance, attribute, value)


@pytest.mark.parametrize(
    "cls",
    [Section, Chunk, Document, VectorRecord, SinkUpsertResult, IngestStageReport, IngestResult],
)
def test_all_domain_dataclasses_use_slots(cls: DomainDataclass) -> None:
    assert hasattr(cls, "__slots__")


def test_document_default_values_work() -> None:
    document = _make_document()

    assert document.source_type == "markdown"
    assert document.frontmatter == {}
    assert document.source_metadata == {}
    assert document.body_markdown == ""
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
    record = VectorRecord(id=uuid.uuid4(), text="vector text")
    sink_result = SinkUpsertResult()
    stage_report = IngestStageReport(stage="run", elapsed_ms=1.0)
    result = IngestResult(documents=(document,), stage_reports=(stage_report,))

    assert section.document_id == document_id
    assert chunk.section_id == section.id
    assert document.title == "Example"
    assert record.metadata == {}
    assert sink_result.updated_source_uris == ()
    assert stage_report.input_count == 0
    assert result.documents == (document,)
    assert result.stage_reports == (stage_report,)


def test_ingest_stage_report_default_values_work() -> None:
    report = IngestStageReport(stage="parse", elapsed_ms=12.5)

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
    assert result.stage_reports == ()
    assert result.persisted is False
    assert result.sink_name is None


def test_metadata_fields_use_metadata_type_alias() -> None:
    assert Document.__annotations__["frontmatter"] == "Metadata"
    assert Document.__annotations__["source_metadata"] == "Metadata"
    assert VectorRecord.__annotations__["metadata"] == "Metadata"
    assert Metadata is not None
