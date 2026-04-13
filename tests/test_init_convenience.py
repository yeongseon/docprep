"""Tests for __init__.py convenience re-export functions."""

from __future__ import annotations

from pathlib import Path

import docprep
from docprep.models.domain import TextPrependStrategy


def _ingest_one(tmp_path: Path) -> tuple[docprep.Document, ...]:
    md = tmp_path / "demo.md"
    _ = md.write_text("# Hello\n\nWorld\n", encoding="utf-8")
    result = docprep.ingest(str(md))
    return result.documents


def test_build_vector_records(tmp_path: Path) -> None:
    docs = _ingest_one(tmp_path)
    records = docprep.build_vector_records(docs)
    assert len(records) >= 1
    assert isinstance(records[0], docprep.VectorRecord)


def test_build_vector_records_with_options(tmp_path: Path) -> None:
    docs = _ingest_one(tmp_path)
    records = docprep.build_vector_records(
        docs,
        text_prepend=TextPrependStrategy.NONE,
        include_annotations=True,
    )
    assert len(records) >= 1


def test_build_vector_records_v1(tmp_path: Path) -> None:
    docs = _ingest_one(tmp_path)
    records = docprep.build_vector_records_v1(docs)
    assert len(records) >= 1
    assert isinstance(records[0], docprep.VectorRecordV1)


def test_build_vector_records_v1_with_created_at(tmp_path: Path) -> None:
    docs = _ingest_one(tmp_path)
    records = docprep.build_vector_records_v1(
        docs,
        created_at="2025-01-01T00:00:00Z",
        include_annotations=True,
    )
    assert len(records) >= 1
    assert records[0].created_at == "2025-01-01T00:00:00Z"


def test_iter_vector_records(tmp_path: Path) -> None:
    docs = _ingest_one(tmp_path)
    records = list(docprep.iter_vector_records(docs))
    assert len(records) >= 1
    assert isinstance(records[0], docprep.VectorRecord)


def test_iter_vector_records_with_options(tmp_path: Path) -> None:
    docs = _ingest_one(tmp_path)
    records = list(
        docprep.iter_vector_records(
            docs,
            text_prepend=TextPrependStrategy.NONE,
            include_annotations=True,
        )
    )
    assert len(records) >= 1


def test_iter_vector_records_v1(tmp_path: Path) -> None:
    docs = _ingest_one(tmp_path)
    records = list(docprep.iter_vector_records_v1(docs))
    assert len(records) >= 1
    assert isinstance(records[0], docprep.VectorRecordV1)


def test_iter_vector_records_v1_with_options(tmp_path: Path) -> None:
    docs = _ingest_one(tmp_path)
    records = list(
        docprep.iter_vector_records_v1(
            docs,
            created_at="2025-06-01T00:00:00Z",
            include_annotations=True,
        )
    )
    assert len(records) >= 1


def test_build_export_delta(tmp_path: Path) -> None:
    docs = _ingest_one(tmp_path)
    diffs = tuple(docprep.compute_diff_from_documents(None, doc) for doc in docs)
    delta = docprep.build_export_delta(diffs, docs)
    assert isinstance(delta, docprep.ExportDelta)
    assert len(delta.added) >= 1


def test_build_export_delta_with_options(tmp_path: Path) -> None:
    docs = _ingest_one(tmp_path)
    diffs = tuple(docprep.compute_diff_from_documents(None, doc) for doc in docs)
    delta = docprep.build_export_delta(
        diffs,
        docs,
        text_prepend=TextPrependStrategy.NONE,
        created_at="2025-06-01",
        include_annotations=True,
    )
    assert isinstance(delta, docprep.ExportDelta)
