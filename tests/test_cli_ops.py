from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from docprep.cli import main as cli_main
from docprep.sinks.sqlalchemy import SQLAlchemySink
from tests.test_cli import _reset_ingest_logger


def _ingest_to_db(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    if files is None:
        files = {"guide.md": "# Title\n\nBody text\n"}

    for name, content in files.items():
        file_path = tmp_path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        _ = file_path.write_text(content, encoding="utf-8")

    db_path = tmp_path / "docs.db"
    _reset_ingest_logger()
    assert cli_main.main(["ingest", str(tmp_path), "--db", f"sqlite:///{db_path}"]) == 0
    return db_path


def _init_empty_db(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    _ = SQLAlchemySink(engine=engine, create_tables=True)


def _get_doc(tmp_path: Path, db_path: Path, source_uri: str):
    del tmp_path
    sink = SQLAlchemySink(engine=create_engine(f"sqlite:///{db_path}"), create_tables=False)
    document = sink.get_document(source_uri)
    assert document is not None
    return document


def test_diff_new_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "docs.db"
    _init_empty_db(db_path)
    _ = (tmp_path / "guide.md").write_text("# Guide\n\nBody\n", encoding="utf-8")

    exit_code = cli_main.main(["diff", str(tmp_path), "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "file:guide.md (new)" in captured.out
    assert "sections: 1 added" in captured.out


def test_diff_unchanged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["diff", str(tmp_path), "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Summary: 0 documents changed, 1 unchanged" in captured.out


def test_diff_modified(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()
    _ = (tmp_path / "guide.md").write_text("# Title\n\nBody text changed\n", encoding="utf-8")

    exit_code = cli_main.main(["diff", str(tmp_path), "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "modified" in captured.out
    assert "Summary: 1 documents changed, 0 unchanged" in captured.out


def test_diff_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["diff", str(tmp_path), "--db", f"sqlite:///{db_path}", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert isinstance(payload, list)
    assert payload[0]["source_uri"] == "file:guide.md"


def test_inspect_document_by_uri(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", "file:guide.md", "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Document: Title" in captured.out
    assert "URI: file:guide.md" in captured.out


def test_inspect_by_uuid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()
    document = _get_doc(tmp_path, db_path, "file:guide.md")

    exit_code = cli_main.main(["inspect", str(document.id), "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Document: Title" in captured.out


def test_inspect_not_found(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["inspect", "file:missing.md", "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "No record found for query" in captured.err


def test_inspect_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(
        ["inspect", "file:guide.md", "--db", f"sqlite:///{db_path}", "--json"]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["source_uri"] == "file:guide.md"


def test_prune_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(
        tmp_path, {"guide.md": "# Guide\n\nBody\n", "old.md": "# Old\n\nBody\n"}
    )
    _ = capsys.readouterr()
    (tmp_path / "old.md").unlink()

    exit_code = cli_main.main(["prune", str(tmp_path), "--db", f"sqlite:///{db_path}", "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[DRY RUN] Would prune 1 document(s):" in captured.out
    assert "file:old.md" in captured.out
    assert _get_doc(tmp_path, db_path, "file:old.md") is not None


def test_prune(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(
        tmp_path, {"guide.md": "# Guide\n\nBody\n", "old.md": "# Old\n\nBody\n"}
    )
    _ = capsys.readouterr()
    (tmp_path / "old.md").unlink()

    exit_code = cli_main.main(["prune", str(tmp_path), "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Pruned 1 document(s):" in captured.out
    sink = SQLAlchemySink(engine=create_engine(f"sqlite:///{db_path}"), create_tables=False)
    assert sink.get_document("file:old.md") is None


def test_prune_uses_uri_in_scope_from_scope_module(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = _ingest_to_db(
        tmp_path, {"guide.md": "# Guide\n\nBody\n", "old.md": "# Old\n\nBody\n"}
    )
    _ = capsys.readouterr()
    (tmp_path / "old.md").unlink()

    monkeypatch.setattr("docprep.scope.uri_in_scope", lambda _uri, _scope: False)
    exit_code = cli_main.main(["prune", str(tmp_path), "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Pruned 0 document(s)." in captured.out
    assert _get_doc(tmp_path, db_path, "file:old.md") is not None


def test_delete(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["delete", "file:guide.md", "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Deleted 1 document: file:guide.md" in captured.out
    sink = SQLAlchemySink(engine=create_engine(f"sqlite:///{db_path}"), create_tables=False)
    assert sink.get_document("file:guide.md") is None


def test_delete_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(
        ["delete", "file:guide.md", "--db", f"sqlite:///{db_path}", "--dry-run"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[DRY RUN] Would delete 1 document: file:guide.md" in captured.out
    assert _get_doc(tmp_path, db_path, "file:guide.md") is not None


def test_delete_not_found(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["delete", "file:missing.md", "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Deleted 0 document(s)." in captured.out


def test_delete_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = _ingest_to_db(tmp_path)
    _ = capsys.readouterr()

    exit_code = cli_main.main(["delete", "file:guide.md", "--db", f"sqlite:///{db_path}", "--json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["deleted_source_uris"] == ["file:guide.md"]
    assert payload["deleted_document_count"] == 1
