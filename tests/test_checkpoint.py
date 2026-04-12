from __future__ import annotations

import json
from pathlib import Path

from docprep.checkpoint import CheckpointStore, compute_config_fingerprint


def test_checkpoint_store_save_and_load(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    store = CheckpointStore(path=checkpoint_path)
    store.load("fp-a")
    store.mark_completed("file:a.md", "checksum-a")
    store.mark_completed("file:b.md", "checksum-b")
    store.save("run-1")

    restored = CheckpointStore(path=checkpoint_path)
    restored.load("fp-a")

    assert restored.is_completed("file:a.md", "checksum-a")
    assert restored.is_completed("file:b.md", "checksum-b")
    assert restored.completed_count == 2


def test_checkpoint_store_config_invalidation(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    store = CheckpointStore(path=checkpoint_path)
    store.load("fp-a")
    store.mark_completed("file:a.md", "checksum-a")
    store.save("run-1")

    restored = CheckpointStore(path=checkpoint_path)
    restored.load("fp-b")

    assert restored.completed_count == 0
    assert not restored.is_completed("file:a.md", "checksum-a")


def test_checkpoint_store_is_completed(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    store = CheckpointStore(path=checkpoint_path)
    store.load("fp-a")
    store.mark_completed("file:a.md", "checksum-a")

    assert store.is_completed("file:a.md", "checksum-a")
    assert not store.is_completed("file:a.md", "checksum-b")
    assert not store.is_completed("file:b.md", "checksum-a")


def test_checkpoint_store_version_mismatch(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    payload = {
        "version": 999,
        "run_id": "run-1",
        "config_fingerprint": "fp-a",
        "completed_sources": {"file:a.md": "checksum-a"},
    }
    checkpoint_path.write_text(json.dumps(payload), encoding="utf-8")

    store = CheckpointStore(path=checkpoint_path)
    store.load("fp-a")

    assert store.completed_count == 0
    assert not store.is_completed("file:a.md", "checksum-a")


def test_checkpoint_store_corrupt_file(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint_path.write_text("not json", encoding="utf-8")

    store = CheckpointStore(path=checkpoint_path)
    store.load("fp-a")

    assert store.completed_count == 0


def test_config_fingerprint_stability() -> None:
    fp_a = compute_config_fingerprint(
        loader_config={"type": "filesystem", "include_globs": ["**/*.md"]},
        parser_config={"type": "auto"},
        chunker_configs=[{"type": "heading"}, {"type": "size", "max_chars": 500}],
    )
    fp_b = compute_config_fingerprint(
        loader_config={"type": "filesystem", "include_globs": ["**/*.md"]},
        parser_config={"type": "auto"},
        chunker_configs=[{"type": "heading"}, {"type": "size", "max_chars": 500}],
    )

    assert fp_a == fp_b


def test_config_fingerprint_different_configs() -> None:
    fp_a = compute_config_fingerprint(chunker_configs=[{"type": "size", "max_chars": 500}])
    fp_b = compute_config_fingerprint(chunker_configs=[{"type": "size", "max_chars": 900}])

    assert fp_a != fp_b
