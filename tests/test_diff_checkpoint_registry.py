"""Tests for diff.py, checkpoint.py, and registry.py uncovered paths."""

from __future__ import annotations

import json
from pathlib import Path
import uuid

import pytest

from docprep.checkpoint import CheckpointStore, compute_config_fingerprint
from docprep.diff import compute_diff, compute_diff_from_documents
from docprep.models.domain import Document, IngestResult, Section
from docprep.registry import _builtin_components, resolve_component

# --- diff.py error cases ---


def _doc(source_uri: str = "file:a.md") -> Document:
    return Document(
        id=uuid.uuid4(),
        source_uri=source_uri,
        title="Test",
        source_checksum="abc",
        sections=(
            Section(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                order_index=0,
                content_markdown="body",
            ),
        ),
    )


def _result(*docs: Document) -> IngestResult:
    return IngestResult(documents=docs)


def test_compute_diff_previous_must_be_single() -> None:
    with pytest.raises(ValueError, match="exactly one document"):
        compute_diff(
            _result(_doc(), _doc()),
            _result(_doc()),
        )


def test_compute_diff_current_must_be_single() -> None:
    with pytest.raises(ValueError, match="exactly one document"):
        compute_diff(
            _result(_doc()),
            _result(_doc(), _doc()),
        )


def test_compute_diff_source_uri_mismatch() -> None:
    with pytest.raises(ValueError, match="share source_uri"):
        compute_diff(
            _result(_doc("file:a.md")),
            _result(_doc("file:b.md")),
        )


def test_compute_diff_from_documents_source_uri_mismatch() -> None:
    with pytest.raises(ValueError, match="share source_uri"):
        compute_diff_from_documents(_doc("file:a.md"), _doc("file:b.md"))


# --- checkpoint.py edge cases ---


def test_checkpoint_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    _ = path.write_text("not json", encoding="utf-8")

    store = CheckpointStore(path=path)
    store.load("fp123")
    # Should gracefully handle malformed JSON and start fresh
    assert store.completed_count == 0


def test_checkpoint_invalid_root_type(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    _ = path.write_text('"just a string"', encoding="utf-8")

    store = CheckpointStore(path=path)
    store.load("fp123")
    assert store.completed_count == 0


def test_checkpoint_invalid_field_types(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    _ = path.write_text(
        json.dumps({"config_fingerprint": 123, "version": "bad", "completed_sources": {}}),
        encoding="utf-8",
    )
    store = CheckpointStore(path=path)
    store.load("fp123")
    assert store.completed_count == 0


def test_checkpoint_config_fingerprint_change(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    _ = path.write_text(
        json.dumps(
            {
                "version": 1,
                "config_fingerprint": "old_fp",
                "run_id": "run1",
                "completed_sources": {"file:a.md": "checksum"},
            }
        ),
        encoding="utf-8",
    )
    store = CheckpointStore(path=path)
    store.load("new_fp")
    # Fingerprint changed -> state reset
    assert store.completed_count == 0


def test_checkpoint_clear(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    store = CheckpointStore(path=path)
    store.load("fp1")
    store.mark_completed("file:a.md", "sum1")
    store.save("run1")
    assert path.exists()

    store.clear()
    assert not path.exists()


def test_checkpoint_clear_nonexistent(tmp_path: Path) -> None:
    path = tmp_path / "nonexistent.json"
    store = CheckpointStore(path=path)
    # Should not raise
    store.clear()


def test_checkpoint_version_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    _ = path.write_text(
        json.dumps(
            {
                "version": 999,
                "config_fingerprint": "fp1",
                "run_id": "run1",
                "completed_sources": {"file:a.md": "checksum"},
            }
        ),
        encoding="utf-8",
    )
    store = CheckpointStore(path=path)
    store.load("fp1")
    # Version mismatch -> state reset
    assert store.completed_count == 0


def test_checkpoint_completed_sources_non_string_filtered(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    _ = path.write_text(
        json.dumps(
            {
                "version": 1,
                "config_fingerprint": "fp1",
                "run_id": "run1",
                "completed_sources": {"file:a.md": "sum1", "file:b.md": 123},
            }
        ),
        encoding="utf-8",
    )
    store = CheckpointStore(path=path)
    store.load("fp1")
    # Only string values should be kept
    assert store.is_completed("file:a.md", "sum1")
    assert not store.is_completed("file:b.md", "123")


def test_checkpoint_run_id_non_string(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    _ = path.write_text(
        json.dumps(
            {
                "version": 1,
                "config_fingerprint": "fp1",
                "run_id": 42,
                "completed_sources": {},
            }
        ),
        encoding="utf-8",
    )
    store = CheckpointStore(path=path)
    store.load("fp1")
    assert store.completed_count == 0


# --- registry.py edge cases ---


def test_builtin_components_unknown_group() -> None:
    with pytest.raises(ValueError, match="Unknown component group"):
        _builtin_components("docprep.nonexistent")


def test_resolve_component_unknown_raises() -> None:
    with pytest.raises(LookupError, match="Unknown component"):
        resolve_component("docprep.chunkers", "nonexistent_chunker")


def test_resolve_component_builtin_chunker() -> None:
    from docprep.chunkers.token import TokenChunker

    result = resolve_component("docprep.chunkers", "token")
    assert result is TokenChunker


def test_compute_config_fingerprint_defaults() -> None:
    fp = compute_config_fingerprint()
    assert len(fp) == 16  # sha256 hex, first 16 chars
