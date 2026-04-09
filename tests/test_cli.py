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


def test_ingest_command_with_config_flag_uses_config_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _ = (docs_dir / "guide.md").write_text("# Title\n\nBody\n", encoding="utf-8")
    config_path = tmp_path / "docprep.toml"
    _ = config_path.write_text("source = 'docs'\n", encoding="utf-8")

    exit_code = cli_main.main(["ingest", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ingested 1 document(s)" in captured.out


def test_cli_source_overrides_config_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_docs = tmp_path / "config-docs"
    config_docs.mkdir()
    _ = (config_docs / "config.md").write_text("# Config Title\n\nBody\n", encoding="utf-8")
    explicit = tmp_path / "explicit.md"
    _ = explicit.write_text("# Explicit Title\n\nBody\n", encoding="utf-8")
    config_path = tmp_path / "docprep.toml"
    _ = config_path.write_text("source = 'config-docs'\n", encoding="utf-8")

    exit_code = cli_main.main(["ingest", "--config", str(config_path), str(explicit)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ingested 1 document(s)" in captured.out
    assert "docprep: error" not in captured.err


def test_json_and_no_json_flags_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit) as exc_info:
        _ = cli_main.main(["preview", "docs", "--json", "--no-json"])

    assert exc_info.value.code == 2


def test_no_json_flag_overrides_config_json_true(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _ = (docs_dir / "guide.md").write_text("# Title\n\nBody\n", encoding="utf-8")
    config_path = tmp_path / "docprep.toml"
    _ = config_path.write_text("source = 'docs'\njson = true\n", encoding="utf-8")

    exit_code = cli_main.main(["preview", "--config", str(config_path), "--no-json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Document: Title" in captured.out
    assert '"title"' not in captured.out


def test_config_driven_ingest_without_positional_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _ = (docs_dir / "guide.md").write_text("# Title\n\nBody\n", encoding="utf-8")
    config_path = tmp_path / "docprep.toml"
    _ = config_path.write_text(
        "source = 'docs'\n[loader]\ntype = 'markdown'\n",
        encoding="utf-8",
    )

    exit_code = cli_main.main(["ingest", "--config", str(config_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ingested 1 document(s)" in captured.out


def test_config_driven_stats_without_positional_db(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "guide.md"
    db_path = tmp_path / "docs.db"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")
    assert cli_main.main(["ingest", str(path), "--db", f"sqlite:///{db_path}"]) == 0
    _ = capsys.readouterr()
    config_path = tmp_path / "docprep.toml"
    _ = config_path.write_text(
        "[sink]\ntype = 'sqlalchemy'\ndatabase_url = 'sqlite:///docs.db'\n",
        encoding="utf-8",
    )

    monkeypatch_dir = tmp_path
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.chdir(monkeypatch_dir)
        exit_code = cli_main.main(["stats", "--config", str(config_path), "--json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert json.loads(captured.out) == {"documents": 1, "sections": 1, "chunks": 1}


def test_cli_reports_error_when_config_file_does_not_exist(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli_main.main(["ingest", "--config", "/nonexistent/docprep.toml"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "config file not found" in captured.err


def test_cli_reports_error_when_source_and_config_are_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli_main.main(["ingest"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "No source specified" in captured.err


def test_cli_auto_discovers_config_from_parent_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _ = (docs_dir / "guide.md").write_text("# Title\n\nBody\n", encoding="utf-8")
    _ = (tmp_path / "docprep.toml").write_text("source = 'docs'\n", encoding="utf-8")
    nested = tmp_path / "nested" / "child"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    exit_code = cli_main.main(["preview"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Document: Title" in captured.out
