from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

import docprep
from docprep.cli import main as cli_main
from docprep.ids import canonicalize_source_uri, chunk_id, content_hash, document_id
from docprep.plugins import LOADER_GROUP, discover_entry_points
from tests.test_cli import _reset_ingest_logger
from tests.test_plugins import _MockEntryPoint


def test_path_separator_variants_produce_forward_slash_uri_and_stable_document_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs = tmp_path / "docs"
    nested = docs / "sub"
    nested.mkdir(parents=True)
    file_path = nested / "guide.md"
    _ = file_path.write_text("# Guide\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    posix_rel = "docs/sub/guide.md"
    native_rel = posix_rel.replace("/", os.sep)

    posix_uri = canonicalize_source_uri(posix_rel, source_root="docs")
    native_uri = canonicalize_source_uri(native_rel, source_root="docs")

    assert posix_uri == native_uri == "file:sub/guide.md"
    assert "\\" not in native_uri
    assert document_id(posix_uri) == document_id(native_uri)


def test_chunk_ids_are_deterministic_for_separator_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    file_path = docs / "guide.md"
    _ = file_path.write_text("# Guide\n\nBody\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    uri_slash = canonicalize_source_uri("docs/guide.md", source_root="docs")
    uri_native = canonicalize_source_uri(f"docs{os.sep}guide.md", source_root="docs")

    chunk_anchor = f"intro:{content_hash('Body')}"
    slash_chunk_id = chunk_id(document_id(uri_slash), chunk_anchor)
    native_chunk_id = chunk_id(document_id(uri_native), chunk_anchor)

    assert uri_slash == uri_native == "file:guide.md"
    assert slash_chunk_id == native_chunk_id


def test_cli_full_lifecycle_ingest_diff_export_changed_only_and_prune(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    guide = docs / "guide.md"
    keep = docs / "keep.md"
    _ = guide.write_text("# Guide\n\nInitial body\n", encoding="utf-8")
    _ = keep.write_text("# Keep\n\nStable body\n", encoding="utf-8")

    db_path = tmp_path / "docs.db"
    db_url = f"sqlite:///{db_path}"

    _reset_ingest_logger()
    assert cli_main.main(["ingest", str(docs), "--db", db_url]) == 0
    ingested = capsys.readouterr()
    assert "Ingested 2 document(s)" in ingested.out

    assert cli_main.main(["diff", str(docs), "--db", db_url]) == 0
    first_diff = capsys.readouterr()
    assert "Summary: 0 documents changed, 2 unchanged" in first_diff.out

    _ = guide.write_text("# Guide\n\nUpdated body\n", encoding="utf-8")
    assert cli_main.main(["diff", str(docs), "--db", db_url]) == 0
    second_diff = capsys.readouterr()
    assert "modified" in second_diff.out
    assert "Summary: 1 documents changed, 1 unchanged" in second_diff.out

    export_path = tmp_path / "changed.jsonl"
    assert (
        cli_main.main(
            [
                "export",
                str(docs),
                "--db",
                db_url,
                "--changed-only",
                "-o",
                str(export_path),
            ]
        )
        == 0
    )
    exported = capsys.readouterr()
    assert "Exported " in exported.err
    assert export_path.read_bytes()

    keep.unlink()
    assert cli_main.main(["prune", str(docs), "--db", db_url]) == 0
    pruned = capsys.readouterr()
    assert "Pruned 1 document" in pruned.out


def test_export_jsonl_is_byte_identical_across_two_runs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _ = (docs / "guide.md").write_text("# Guide\n\nDeterministic body\n", encoding="utf-8")

    first_db = tmp_path / "first.db"
    second_db = tmp_path / "second.db"
    first_out = tmp_path / "first.jsonl"
    second_out = tmp_path / "second.jsonl"

    class _FixedDateTime:
        @staticmethod
        def now(tz: timezone) -> datetime:
            del tz
            return datetime(2024, 1, 1, tzinfo=timezone.utc)

    with patch("docprep.export.datetime", _FixedDateTime):
        _reset_ingest_logger()
        assert cli_main.main(["ingest", str(docs), "--db", f"sqlite:///{first_db}"]) == 0
        _ = capsys.readouterr()
        assert (
            cli_main.main(
                ["export", str(docs), "--db", f"sqlite:///{first_db}", "-o", str(first_out)]
            )
            == 0
        )
        _ = capsys.readouterr()

        _reset_ingest_logger()
        assert cli_main.main(["ingest", str(docs), "--db", f"sqlite:///{second_db}"]) == 0
        _ = capsys.readouterr()
        assert (
            cli_main.main(
                ["export", str(docs), "--db", f"sqlite:///{second_db}", "-o", str(second_out)]
            )
            == 0
        )
        _ = capsys.readouterr()

    assert first_out.read_bytes() == second_out.read_bytes()


def test_plugin_import_failure_warning_is_actionable() -> None:
    broken = _MockEntryPoint(
        "broken-loader",
        "broken.module:Loader",
        error=ImportError("missing optional dependency"),
    )

    with patch("docprep.plugins.importlib.metadata.entry_points", return_value=[broken]):
        with pytest.warns(RuntimeWarning) as warnings_record:
            discovered = discover_entry_points(LOADER_GROUP)

    assert discovered == {}
    assert len(warnings_record) == 1
    warning_message = str(warnings_record[0].message)
    assert "broken-loader" in warning_message
    assert LOADER_GROUP in warning_message
    assert "broken.module:Loader" in warning_message
    assert "missing optional dependency" in warning_message
    assert "Check that the package and its dependencies are installed correctly" in warning_message


def test_python_module_version_subprocess_smoke() -> None:
    completed = subprocess.run(
        ["python3", "-m", "docprep", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert docprep.__version__ in completed.stdout
