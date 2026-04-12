from __future__ import annotations

from collections.abc import Callable
import importlib
import json
from pathlib import Path
import runpy
import sys
from typing import cast

import pytest

import docprep
from docprep.cli import main as cli_main
from docprep.exceptions import DocPrepError
from docprep.models.domain import DocumentError, IngestResult, PipelineStage


def _reset_ingest_logger() -> None:
    import logging

    logger = logging.getLogger("docprep.ingest")
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)


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
    _reset_ingest_logger()
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
    _reset_ingest_logger()
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
    _reset_ingest_logger()
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
    _reset_ingest_logger()
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
    _reset_ingest_logger()
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
    _reset_ingest_logger()
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
    _reset_ingest_logger()
    exit_code = cli_main.main(["ingest", "--config", "/nonexistent/docprep.toml"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "config file not found" in captured.err


def test_cli_reports_error_when_source_and_config_are_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _reset_ingest_logger()
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


def test_ingest_command_uses_human_log_format_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _reset_ingest_logger()
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    exit_code = cli_main.main(["ingest", str(path), "--log-format", "human"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[info] [load] Loaded 1 source(s)" in captured.err
    assert "[info] [run] Run completed: 1 processed, 0 failed" in captured.err


def test_ingest_command_uses_json_log_format(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _reset_ingest_logger()
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    exit_code = cli_main.main(["ingest", str(path), "--log-format", "json"])

    captured = capsys.readouterr()
    assert exit_code == 0
    entries = [json.loads(line) for line in captured.err.splitlines() if line.strip()]
    assert entries[0]["level"] == "info"
    assert entries[0]["stage"] == "load"
    assert entries[-1]["stage"] == "run"
    assert entries[-1]["processed_count"] == 1


def test_ingest_command_uses_debug_log_level(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _reset_ingest_logger()
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    exit_code = cli_main.main(["ingest", str(path), "--log-level", "debug"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Parsed " in captured.err


def test_ingest_command_uses_error_log_level(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _reset_ingest_logger()
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    exit_code = cli_main.main(["ingest", str(path), "--log-level", "error"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""


def test_ingest_command_accepts_error_mode_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _reset_ingest_logger()
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    exit_code = cli_main.main(["ingest", str(path), "--error-mode", "fail_fast"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ingested 1 document(s)" in captured.out


def test_ingest_command_accepts_workers_flag(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_workers: list[int] = []

    class FakeIngestor:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def run(
            self,
            source: object,
            workers: int = 1,
            resume: bool = False,
            checkpoint_path: str | None = None,
        ) -> IngestResult:
            del source
            del resume
            del checkpoint_path
            captured_workers.append(workers)
            return IngestResult(documents=(), processed_count=1)

    ingest_module = importlib.import_module("docprep.ingest")
    monkeypatch.setattr(ingest_module, "Ingestor", FakeIngestor)

    exit_code = cli_main.main(["ingest", "docs", "--workers", "4"])

    _ = capsys.readouterr()
    assert exit_code == 0
    assert captured_workers == [4]


def test_ingest_command_returns_partial_success_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeIngestor:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def run(
            self,
            source: object,
            workers: int = 1,
            resume: bool = False,
            checkpoint_path: str | None = None,
        ) -> IngestResult:
            del source
            del workers
            del resume
            del checkpoint_path
            return IngestResult(
                documents=(),
                processed_count=1,
                failed_count=1,
                failed_source_uris=("docs/bad.md",),
                errors=(
                    DocumentError(
                        source_uri="docs/bad.md",
                        stage=PipelineStage.PARSE,
                        error_type="RuntimeError",
                        message="bad parse",
                    ),
                ),
            )

    ingest_module = importlib.import_module("docprep.ingest")
    monkeypatch.setattr(ingest_module, "Ingestor", FakeIngestor)
    exit_code = cli_main.main(["ingest", "docs"])

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "Failed: 1" in captured.out


def test_ingest_command_returns_failure_exit_code_when_all_failed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeIngestor:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def run(
            self,
            source: object,
            workers: int = 1,
            resume: bool = False,
            checkpoint_path: str | None = None,
        ) -> IngestResult:
            del source
            del workers
            del resume
            del checkpoint_path
            return IngestResult(
                documents=(),
                processed_count=0,
                failed_count=1,
                failed_source_uris=("docs/bad.md",),
                errors=(
                    DocumentError(
                        source_uri="docs/bad.md",
                        stage=PipelineStage.PARSE,
                        error_type="RuntimeError",
                        message="bad parse",
                    ),
                ),
            )

    ingest_module = importlib.import_module("docprep.ingest")
    monkeypatch.setattr(ingest_module, "Ingestor", FakeIngestor)
    exit_code = cli_main.main(["ingest", "docs"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Failed: 1" in captured.out


def test_cli_ingest_resume_flag(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured_resume: list[bool] = []
    captured_checkpoint_path: list[str | None] = []

    class FakeIngestor:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def run(
            self,
            source: object,
            workers: int = 1,
            resume: bool = False,
            checkpoint_path: str | None = None,
        ) -> IngestResult:
            del source
            del workers
            captured_resume.append(resume)
            captured_checkpoint_path.append(checkpoint_path)
            return IngestResult(documents=(), processed_count=1)

    ingest_module = importlib.import_module("docprep.ingest")
    monkeypatch.setattr(ingest_module, "Ingestor", FakeIngestor)

    exit_code = cli_main.main(
        ["ingest", "docs", "--resume", "--checkpoint-path", "/tmp/custom-checkpoint.json"]
    )

    _ = capsys.readouterr()
    assert exit_code == 0
    assert captured_resume == [True]
    assert captured_checkpoint_path == ["/tmp/custom-checkpoint.json"]
