from __future__ import annotations

import json
from typing import cast
import uuid

from docprep.cli.formatters import format_ingest_result, format_preview, format_stats
from docprep.models.domain import Chunk, Document, IngestResult, IngestStageReport, Section


def _document() -> Document:
    doc_id = uuid.uuid4()
    section = Section(
        id=uuid.uuid4(),
        document_id=doc_id,
        order_index=0,
        heading="Intro",
        heading_level=1,
        heading_path=("Intro",),
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
    )
    return Document(
        id=doc_id,
        source_uri="docs/example.md",
        title="Example",
        source_checksum="1234567890abcdef",
        sections=(section,),
        chunks=(chunk,),
    )


def test_format_ingest_result_text_output() -> None:
    result = IngestResult(
        documents=(_document(),),
        processed_count=1,
        skipped_count=1,
        skipped_source_uris=("docs/example.md",),
        persisted=True,
        sink_name="SQLAlchemySink",
    )

    assert format_ingest_result(result) == (
        "Ingested 1 document(s)\n"
        "  Processed: 1\n"
        "  Skipped (unchanged): 1\n"
        "Persisted via: SQLAlchemySink"
    )


def test_format_ingest_result_json_output() -> None:
    result = IngestResult(
        documents=(_document(),),
        processed_count=1,
        updated_count=1,
        skipped_count=0,
        failed_count=0,
        deleted_count=0,
        updated_source_uris=("docs/example.md",),
        persisted=False,
        sink_name=None,
    )

    assert json.loads(format_ingest_result(result, as_json=True)) == {
        "documents_count": 1,
        "processed_count": 1,
        "updated_count": 1,
        "skipped_count": 0,
        "failed_count": 0,
        "deleted_count": 0,
        "skipped_source_uris": [],
        "updated_source_uris": ["docs/example.md"],
        "failed_source_uris": [],
        "deleted_source_uris": [],
        "persisted": False,
        "sink_name": None,
    }


def test_format_ingest_result_includes_stage_reports() -> None:
    result = IngestResult(
        documents=(_document(),),
        processed_count=1,
        stage_reports=(
            IngestStageReport(
                stage="load",
                elapsed_ms=12.345,
                input_count=0,
                output_count=1,
            ),
            IngestStageReport(
                stage="run",
                elapsed_ms=45.678,
                input_count=1,
                output_count=1,
                failed_count=0,
            ),
        ),
    )

    assert format_ingest_result(result) == (
        "Ingested 1 document(s)\n"
        "  Processed: 1\n"
        "Stage timings:\n"
        "  load: 12.3ms\n"
        "  run: 45.7ms"
    )

    assert json.loads(format_ingest_result(result, as_json=True))["stage_reports"] == [
        {
            "stage": "load",
            "elapsed_ms": 12.35,
            "input_count": 0,
            "output_count": 1,
            "failed_count": 0,
        },
        {
            "stage": "run",
            "elapsed_ms": 45.68,
            "input_count": 1,
            "output_count": 1,
            "failed_count": 0,
        },
    ]


def test_format_ingest_result_includes_failed_count() -> None:
    result = IngestResult(documents=(), processed_count=0, failed_count=2)

    assert format_ingest_result(result) == "Ingested 0 document(s)\n  Processed: 0\n  Failed: 2"


def test_format_preview_text_output() -> None:
    output = format_preview((_document(),))

    assert "Document: Example" in output
    assert "Source: docs/example.md" in output
    assert "[1] Intro" in output


def test_format_preview_json_output() -> None:
    output = cast(list[dict[str, object]], json.loads(format_preview((_document(),), as_json=True)))
    first = output[0]
    sections = cast(list[dict[str, object]], first["sections"])

    assert first["title"] == "Example"
    assert first["sections_count"] == 1
    assert sections[0] == {
        "heading": "Intro",
        "heading_level": 1,
        "heading_path": ["Intro"],
    }


def test_format_stats_text_output() -> None:
    assert format_stats({"documents": 1, "sections": 2, "chunks": 3}) == (
        "documents: 1\nsections: 2\nchunks: 3"
    )


def test_format_stats_json_output() -> None:
    assert json.loads(format_stats({"documents": 1}, as_json=True)) == {"documents": 1}
