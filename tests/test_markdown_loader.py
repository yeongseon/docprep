from __future__ import annotations

from pathlib import Path

import pytest

from docprep.exceptions import LoadError
from docprep.ids import sha256_checksum
from docprep.loaders.markdown import MarkdownLoader


def test_load_single_markdown_file(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Guide\n", encoding="utf-8")

    loaded = list(MarkdownLoader().load(path))

    assert len(loaded) == 1
    assert loaded[0].source_path == str(path)
    assert loaded[0].raw_text == "# Guide\n"


def test_load_directory_with_multiple_markdown_files_in_sorted_order(tmp_path: Path) -> None:
    _ = (tmp_path / "b.md").write_text("B", encoding="utf-8")
    _ = (tmp_path / "a.md").write_text("A", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    _ = (tmp_path / "nested" / "c.md").write_text("C", encoding="utf-8")

    loaded = list(MarkdownLoader().load(tmp_path))

    assert [Path(item.source_path).name for item in loaded] == ["a.md", "b.md", "c.md"]


def test_load_raises_for_nonexistent_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing.md"

    with pytest.raises(LoadError, match="does not exist"):
        _ = list(MarkdownLoader().load(missing))


def test_load_raises_for_unreadable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "bad.md"
    _ = path.write_text("broken", encoding="utf-8")

    def failing_read_text(self: Path, *, encoding: str) -> str:
        del self, encoding
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "read_text", failing_read_text)

    with pytest.raises(LoadError, match="Failed to read"):
        _ = list(MarkdownLoader().load(path))


def test_custom_glob_pattern_filters_files(tmp_path: Path) -> None:
    _ = (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")
    _ = (tmp_path / "skip.md").write_text("skip", encoding="utf-8")

    loaded = list(MarkdownLoader(glob_pattern="**/*.txt").load(tmp_path))

    assert [Path(item.source_path).name for item in loaded] == ["keep.txt"]


def test_checksum_is_computed_correctly(tmp_path: Path) -> None:
    content = "# Guide\n\nBody\n"
    path = tmp_path / "guide.md"
    _ = path.write_text(content, encoding="utf-8")

    loaded = next(iter(MarkdownLoader().load(path)))

    assert loaded.checksum == sha256_checksum(content)


def test_source_uri_is_canonical_file_uri(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Guide\n", encoding="utf-8")

    loaded = next(iter(MarkdownLoader().load(path)))

    assert loaded.source_uri == "file:guide.md"
