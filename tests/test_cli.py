from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import runpy
import sys
from typing import cast

import pytest

import docprep
from docprep.cli import main as cli_main
from docprep.exceptions import DocPrepError


def test_help_exits_with_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _ = cli_main.main(["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "Prepare documents into structured" in captured.out


def test_version_shows_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _ = cli_main.main(["--version"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert docprep.__version__ in captured.out


def test_ingest_command_with_temp_file_works(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "guide.md"
    db_path = tmp_path / "docs.db"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    exit_code = cli_main.main(["ingest", str(path), "--db", f"sqlite:///{db_path}"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ingested 1 document(s)" in captured.out
    assert "Persisted via: SQLAlchemySink" in captured.out


def test_preview_command_with_temp_file_works(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    exit_code = cli_main.main(["preview", str(path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Document: Title" in captured.out
    assert "Sections: 1" in captured.out


def test_stats_command_with_temp_db_works(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "guide.md"
    db_path = tmp_path / "docs.db"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")
    assert cli_main.main(["ingest", str(path), "--db", f"sqlite:///{db_path}"]) == 0
    _ = capsys.readouterr()

    exit_code = cli_main.main(["stats", f"sqlite:///{db_path}", "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {"documents": 1, "sections": 1, "chunks": 1}


def test_docprep_error_is_caught_and_returns_exit_code_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def failing_handler(args: object) -> int:
        del args
        raise DocPrepError("boom")

    commands = cast(dict[str, Callable[[object], int]], cli_main.__dict__["_COMMANDS"])
    monkeypatch.setitem(commands, "ingest", failing_handler)

    exit_code = cli_main.main(["ingest", "anything.md"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "docprep: error: boom" in captured.err


def test_missing_command_shows_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _ = cli_main.main([])

    captured = capsys.readouterr()
    assert exc_info.value.code == 2
    assert "the following arguments are required: command" in captured.err


def test_python_m_entrypoint_raises_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["python", "--version"])

    with pytest.raises(SystemExit) as exc_info:
        _ = runpy.run_module("docprep", run_name="__main__")

    assert exc_info.value.code == 0
