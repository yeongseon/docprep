from __future__ import annotations

import json
from typing import cast
import uuid

from docprep.cli.formatters import format_ingest_result, format_preview, format_stats
from docprep.models.domain import Chunk, Document, IngestResult, Section


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
        skipped_source_uris=("docs/example.md",),
        persisted=True,
        sink_name="SQLAlchemySink",
    )

    assert format_ingest_result(result) == (
        "Ingested 1 document(s)\nSkipped (unchanged): 1\nPersisted via: SQLAlchemySink"
    )


def test_format_ingest_result_json_output() -> None:
    result = IngestResult(documents=(_document(),), persisted=False, sink_name=None)

    assert json.loads(format_ingest_result(result, as_json=True)) == {
        "documents_count": 1,
        "skipped_source_uris": [],
        "persisted": False,
        "sink_name": None,
    }


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
