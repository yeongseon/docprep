"""Tests for cli/formatters.py — uncovered format functions."""

from __future__ import annotations

import json
import uuid

from docprep.cli.formatters import (
    format_delete_result,
    format_export_summary,
    format_inspect_chunk,
    format_inspect_section,
)
from docprep.models.domain import Chunk, DeleteResult, Section


def _make_section(
    *,
    heading: str | None = "Introduction",
    heading_level: int = 2,
    anchor: str = "introduction",
    content_hash: str = "abc123",
) -> Section:
    doc_id = uuid.uuid4()
    return Section(
        id=uuid.uuid4(),
        document_id=doc_id,
        order_index=0,
        heading=heading,
        heading_level=heading_level,
        anchor=anchor,
        content_hash=content_hash,
        heading_path=("Introduction",),
        lineage=(str(uuid.uuid4()),),
        content_markdown="Some content",
    )


def _make_chunk(
    *,
    content_text: str = "Hello world",
    anchor: str = "introduction:abc123",
    char_start: int = 0,
    char_end: int = 11,
) -> Chunk:
    doc_id = uuid.uuid4()
    return Chunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        section_id=uuid.uuid4(),
        order_index=0,
        section_chunk_index=0,
        anchor=anchor,
        content_hash="hash123",
        content_text=content_text,
        char_start=char_start,
        char_end=char_end,
        token_count=2,
        heading_path=("Introduction",),
        lineage=(str(uuid.uuid4()),),
    )


# --- format_inspect_section ---


def test_format_inspect_section_text() -> None:
    section = _make_section()
    result = format_inspect_section(section)
    assert "Section: Introduction" in result
    assert "Anchor: introduction" in result
    assert "Level: 2" in result
    assert "Hash: abc123" in result
    assert "Document ID:" in result


def test_format_inspect_section_root() -> None:
    section = _make_section(heading=None)
    result = format_inspect_section(section)
    assert "Section: (root)" in result


def test_format_inspect_section_json() -> None:
    section = _make_section()
    result = format_inspect_section(section, as_json=True)
    data = json.loads(result)
    assert data["heading"] == "Introduction"
    assert data["heading_level"] == 2
    assert data["anchor"] == "introduction"
    assert data["content_hash"] == "abc123"
    assert "document_id" in data
    assert "content_markdown" in data


# --- format_inspect_chunk ---


def test_format_inspect_chunk_text() -> None:
    chunk = _make_chunk()
    result = format_inspect_chunk(chunk)
    assert "Chunk: introduction:abc123" in result
    assert "Hash: hash123" in result
    assert "Section: introduction" in result
    assert "Chars: 0-11" in result
    assert "Text preview:" in result


def test_format_inspect_chunk_long_text() -> None:
    long_text = "word " * 50
    chunk = _make_chunk(content_text=long_text, char_end=len(long_text))
    result = format_inspect_chunk(chunk)
    assert "..." in result


def test_format_inspect_chunk_no_anchor() -> None:
    chunk = _make_chunk(anchor="")
    result = format_inspect_chunk(chunk)
    assert "Chunk:" in result


def test_format_inspect_chunk_json() -> None:
    chunk = _make_chunk()
    result = format_inspect_chunk(chunk, as_json=True)
    data = json.loads(result)
    assert data["content_text"] == "Hello world"
    assert data["char_start"] == 0
    assert data["char_end"] == 11
    assert "section_chunk_index" in data


# --- format_delete_result multi-doc ---


def test_format_delete_result_multi_doc() -> None:
    result = DeleteResult(
        deleted_source_uris=("file:a.md", "file:b.md"),
        deleted_document_count=2,
        deleted_section_count=4,
        deleted_chunk_count=8,
        dry_run=False,
    )
    output = format_delete_result(result)
    assert "Deleted 2 document(s)" in output
    assert "4 sections" in output
    assert "8 chunks" in output
    assert "file:a.md" in output
    assert "file:b.md" in output


def test_format_delete_result_multi_doc_dry_run() -> None:
    result = DeleteResult(
        deleted_source_uris=("file:a.md", "file:b.md"),
        deleted_document_count=2,
        deleted_section_count=4,
        deleted_chunk_count=8,
        dry_run=True,
    )
    output = format_delete_result(result)
    assert "[DRY RUN] Would delete 2 document(s)" in output


def test_format_delete_result_json() -> None:
    result = DeleteResult(
        deleted_source_uris=("file:a.md",),
        deleted_document_count=1,
        deleted_section_count=2,
        deleted_chunk_count=4,
        dry_run=False,
    )
    output = format_delete_result(result, as_json=True)
    data = json.loads(output)
    assert data["deleted_document_count"] == 1
    assert "file:a.md" in data["deleted_source_uris"]


# --- format_export_summary ---


def test_format_export_summary_json() -> None:
    output = format_export_summary(
        records_written=10,
        deleted_written=2,
        changed_only=True,
        as_json=True,
    )
    data = json.loads(output)
    assert data["records_written"] == 10
    assert data["deleted_written"] == 2
    assert data["changed_only"] is True


def test_format_export_summary_changed_only_text() -> None:
    output = format_export_summary(
        records_written=5,
        deleted_written=1,
        changed_only=True,
    )
    assert "5 changed record(s)" in output
    assert "1 deleted ID marker(s)" in output
