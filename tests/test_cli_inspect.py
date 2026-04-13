"""Tests for cli/commands/inspect.py — UUID-based lookups for documents, sections, chunks."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from docprep.cli import main as cli_main
from docprep.sinks.sqlalchemy import SQLAlchemySink
from tests.test_cli import _reset_ingest_logger


def _ingest_and_get_ids(tmp_path: Path) -> tuple[Path, str, str, str, str]:
    """Ingest a file and return (db_path, source_uri, doc_uuid, section_uuid, chunk_uuid)."""
    _ = (tmp_path / "guide.md").write_text("# Guide\n\nBody text\n", encoding="utf-8")
    db_path = tmp_path / "docs.db"
    _reset_ingest_logger()
    assert cli_main.main(["ingest", str(tmp_path), "--db", f"sqlite:///{db_path}"]) == 0

    sink = SQLAlchemySink(engine=create_engine(f"sqlite:///{db_path}"), create_tables=False)
    doc = sink.get_document("file:guide.md")
    assert doc is not None
    doc_uuid = str(doc.id)
    section_uuid = str(doc.sections[0].id)
    chunk_uuid = str(doc.chunks[0].id)
    return db_path, "file:guide.md", doc_uuid, section_uuid, chunk_uuid


def test_inspect_by_source_uri(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path, source_uri, _, _, _ = _ingest_and_get_ids(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", source_uri, "--db", f"sqlite:///{db_path}"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Document:" in captured.out


def test_inspect_by_file_prefix(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path, _, _, _, _ = _ingest_and_get_ids(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", "file:guide.md", "--db", f"sqlite:///{db_path}"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Document:" in captured.out


def test_inspect_by_doc_uuid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path, _, doc_uuid, _, _ = _ingest_and_get_ids(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", doc_uuid, "--db", f"sqlite:///{db_path}"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Document:" in captured.out


def test_inspect_by_section_uuid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path, _, _, section_uuid, _ = _ingest_and_get_ids(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", section_uuid, "--db", f"sqlite:///{db_path}"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Section:" in captured.out


def test_inspect_by_chunk_uuid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path, _, _, _, chunk_uuid = _ingest_and_get_ids(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", chunk_uuid, "--db", f"sqlite:///{db_path}"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Chunk:" in captured.out


def test_inspect_unknown_uuid_returns_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, _, _, _, _ = _ingest_and_get_ids(tmp_path)
    _ = capsys.readouterr()

    import uuid as _uuid

    fake_uuid = str(_uuid.uuid4())
    exit_code = cli_main.main(["inspect", fake_uuid, "--db", f"sqlite:///{db_path}"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "No record found" in captured.err


def test_inspect_unknown_query_returns_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path, _, _, _, _ = _ingest_and_get_ids(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", "nonexistent-query", "--db", f"sqlite:///{db_path}"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "No record found" in captured.err


def test_inspect_doc_uuid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path, _, doc_uuid, _, _ = _ingest_and_get_ids(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", doc_uuid, "--db", f"sqlite:///{db_path}", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    data = json.loads(captured.out)
    assert "id" in data
    assert "sections" in data


def test_inspect_section_uuid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path, _, _, section_uuid, _ = _ingest_and_get_ids(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", section_uuid, "--db", f"sqlite:///{db_path}", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    data = json.loads(captured.out)
    assert "heading" in data


def test_inspect_chunk_uuid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path, _, _, _, chunk_uuid = _ingest_and_get_ids(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", chunk_uuid, "--db", f"sqlite:///{db_path}", "--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    data = json.loads(captured.out)
    assert "content_text" in data
