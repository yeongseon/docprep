from __future__ import annotations

import io
import json
from pathlib import Path
import uuid

import pytest
from sqlalchemy import create_engine

from docprep.cli import main as cli_main
from docprep.diff import compute_diff_from_documents
from docprep.export import (
    ExportDelta,
    build_export_delta,
    build_vector_records,
    build_vector_records_v1,
    iter_vector_records,
    iter_vector_records_v1,
    record_to_jsonl,
    write_jsonl,
)
from docprep.ids import chunk_id, content_hash, document_id, section_id
from docprep.models.domain import Chunk, Document, Section, TextPrependStrategy
from docprep.sinks.sqlalchemy import SQLAlchemySink
from tests.test_cli import _reset_ingest_logger


def _build_document(
    *,
    source_uri: str,
    title: str,
    chunk_entries: tuple[tuple[str, str], ...],
) -> Document:
    doc_id = document_id(source_uri)
    section_anchors: list[str] = []
    for chunk_anchor, _chunk_text in chunk_entries:
        section_anchor = chunk_anchor.split(":", 1)[0]
        if section_anchor not in section_anchors:
            section_anchors.append(section_anchor)

    sections: list[Section] = []
    for index, section_anchor in enumerate(section_anchors):
        sections.append(
            Section(
                id=section_id(doc_id, section_anchor),
                document_id=doc_id,
                order_index=index,
                heading=section_anchor,
                heading_level=1,
                anchor=section_anchor,
                content_hash=content_hash(section_anchor),
                heading_path=(section_anchor,),
                lineage=("root",),
                content_markdown=section_anchor,
            )
        )

    section_ids = {section.anchor: section.id for section in sections}
    chunks: list[Chunk] = []
    for index, (chunk_anchor, chunk_text) in enumerate(chunk_entries):
        section_anchor = chunk_anchor.split(":", 1)[0]
        chunks.append(
            Chunk(
                id=chunk_id(doc_id, chunk_anchor),
                document_id=doc_id,
                section_id=section_ids[section_anchor],
                order_index=index,
                section_chunk_index=0,
                anchor=chunk_anchor,
                content_hash=content_hash(chunk_text),
                content_text=chunk_text,
                heading_path=(section_anchor,),
                lineage=("root",),
            )
        )

    return Document(
        id=doc_id,
        source_uri=source_uri,
        title=title,
        source_checksum=content_hash("\n".join(text for _, text in chunk_entries)),
        source_type="markdown",
        frontmatter={"author": "Ada"},
        source_metadata={"team": "search"},
        body_markdown="\n".join(text for _, text in chunk_entries),
        sections=tuple(sections),
        chunks=tuple(chunks),
    )


def test_iter_vector_records_matches_build_vector_records() -> None:
    document = _build_document(
        source_uri="file:guide.md",
        title="Guide",
        chunk_entries=(("intro:c1", "one"), ("usage:c2", "two")),
    )

    expected = build_vector_records((document,))
    actual = tuple(iter_vector_records((document,)))

    assert actual == expected


def test_iter_vector_records_v1_matches_build_vector_records_v1() -> None:
    document = _build_document(
        source_uri="file:guide.md",
        title="Guide",
        chunk_entries=(("intro:c1", "one"),),
    )

    expected = build_vector_records_v1((document,), created_at="2026-03-01T00:00:00+00:00")
    actual = tuple(iter_vector_records_v1((document,), created_at="2026-03-01T00:00:00+00:00"))

    assert actual == expected


def test_record_to_jsonl_serializes_uuid_fields_as_strings() -> None:
    document = _build_document(
        source_uri="file:guide.md",
        title="Guide",
        chunk_entries=(("intro:c1", "one"),),
    )
    record = build_vector_records_v1((document,), created_at="2026-03-01T00:00:00+00:00")[0]

    payload = json.loads(record_to_jsonl(record))

    assert payload["id"] == str(record.id)
    assert payload["document_id"] == str(record.document_id)
    assert payload["section_id"] == str(record.section_id)


def test_write_jsonl_writes_count_and_parseable_lines() -> None:
    document = _build_document(
        source_uri="file:guide.md",
        title="Guide",
        chunk_entries=(("intro:c1", "one"), ("usage:c2", "two")),
    )
    out = io.StringIO()

    written = write_jsonl(
        iter_vector_records_v1((document,), created_at="2026-03-01T00:00:00+00:00"), out
    )
    lines = [line for line in out.getvalue().splitlines() if line]

    assert written == 2
    assert len(lines) == 2
    assert all(isinstance(json.loads(line), dict) for line in lines)


def test_export_delta_dataclass_defaults() -> None:
    delta = ExportDelta()

    assert delta.added == ()
    assert delta.modified == ()
    assert delta.deleted_ids == ()


def test_build_export_delta_returns_added_modified_and_deleted_records() -> None:
    previous = _build_document(
        source_uri="file:guide.md",
        title="Guide",
        chunk_entries=(("intro:c1", "one"), ("usage:c2", "two-old"), ("old:c3", "gone")),
    )
    current = _build_document(
        source_uri="file:guide.md",
        title="Guide",
        chunk_entries=(("intro:c1", "one"), ("usage:c2", "two-new"), ("new:c4", "fresh")),
    )

    diff = compute_diff_from_documents(previous, current)
    delta = build_export_delta((diff,), (current,), created_at="2026-03-01T00:00:00+00:00")

    assert len(delta.added) == 1
    assert delta.added[0].chunk_anchor == "new:c4"
    assert len(delta.modified) == 1
    assert delta.modified[0].chunk_anchor == "usage:c2"
    assert delta.deleted_ids == (chunk_id(current.id, "old:c3"),)


def test_cli_export_writes_jsonl_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    md = tmp_path / "guide.md"
    _ = md.write_text("# Guide\n\nBody\n", encoding="utf-8")

    exit_code = cli_main.main(["export", str(md)])

    captured = capsys.readouterr()
    lines = [line for line in captured.out.splitlines() if line]
    assert exit_code == 0
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["source_uri"] == "file:guide.md"


def test_cli_export_writes_jsonl_to_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    md = tmp_path / "guide.md"
    _ = md.write_text("# Guide\n\nBody\n", encoding="utf-8")
    output_file = tmp_path / "records.jsonl"

    exit_code = cli_main.main(["export", str(md), "-o", str(output_file)])

    _ = capsys.readouterr()
    assert exit_code == 0
    lines = output_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["source_uri"] == "file:guide.md"


def test_cli_export_changed_only_emits_deleted_markers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _reset_ingest_logger()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _ = (docs_dir / "guide.md").write_text("# Guide\n\nBody\n", encoding="utf-8")
    _ = (docs_dir / "old.md").write_text("# Old\n\nBody\n", encoding="utf-8")
    db_path = tmp_path / "docs.db"

    assert cli_main.main(["ingest", str(docs_dir), "--db", f"sqlite:///{db_path}"]) == 0
    _ = capsys.readouterr()

    sink = SQLAlchemySink(engine=create_engine(f"sqlite:///{db_path}"), create_tables=False)
    previous_old = sink.get_document("file:old.md")
    assert previous_old is not None
    deleted_chunk_id = previous_old.chunks[0].id

    _ = (docs_dir / "guide.md").write_text("# Guide\n\nBody changed\n", encoding="utf-8")
    (docs_dir / "old.md").unlink()

    exit_code = cli_main.main(
        [
            "export",
            str(docs_dir),
            "--changed-only",
            "--db",
            f"sqlite:///{db_path}",
        ]
    )

    captured = capsys.readouterr()
    payloads = [json.loads(line) for line in captured.out.splitlines() if line]
    assert exit_code == 0
    assert any(payload.get("source_uri") == "file:guide.md" for payload in payloads)
    assert any(
        payload.get("_deleted") is True and payload.get("id") == str(deleted_chunk_id)
        for payload in payloads
    )


def test_empty_documents_produce_empty_jsonl_output() -> None:
    out = io.StringIO()
    written = write_jsonl(iter_vector_records_v1(()), out)

    assert written == 0
    assert out.getvalue() == ""


def test_streaming_iterator_handles_large_input_without_tuple_materialization() -> None:
    doc_id = uuid.uuid4()
    section = Section(
        id=uuid.uuid4(),
        document_id=doc_id,
        order_index=0,
        heading="Bulk",
        heading_level=1,
        anchor="bulk",
        content_hash="bulkhash",
        heading_path=("Bulk",),
        lineage=("root",),
        content_markdown="bulk",
    )
    chunks = tuple(
        Chunk(
            id=uuid.uuid4(),
            document_id=doc_id,
            section_id=section.id,
            order_index=index,
            section_chunk_index=index,
            anchor=f"bulk:{index}",
            content_hash=f"h{index}",
            content_text=f"chunk {index}",
            heading_path=("Bulk",),
            lineage=("root",),
        )
        for index in range(2000)
    )
    document = Document(
        id=doc_id,
        source_uri="file:bulk.md",
        title="Bulk",
        source_checksum="bulk",
        sections=(section,),
        chunks=chunks,
    )

    iterator = iter_vector_records((document,), text_prepend=TextPrependStrategy.NONE)

    assert not isinstance(iterator, tuple)
    first = next(iterator)
    assert first.text == "chunk 0"
    remaining = sum(1 for _ in iterator)
    assert remaining == 1999
