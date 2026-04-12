from __future__ import annotations

from pathlib import Path

import pytest

from docprep.exceptions import LoadError
from docprep.loaders.filesystem import FileSystemLoader


def test_filesystem_loader_loads_supported_formats_with_media_types(tmp_path: Path) -> None:
    _ = (tmp_path / "guide.md").write_text("# Guide", encoding="utf-8")
    _ = (tmp_path / "notes.txt").write_text("Notes", encoding="utf-8")
    _ = (tmp_path / "page.html").write_text("<h1>Page</h1>", encoding="utf-8")
    _ = (tmp_path / "legacy.htm").write_text("<h1>Legacy</h1>", encoding="utf-8")

    loaded = list(FileSystemLoader().load(tmp_path))

    assert [Path(item.source_path).name for item in loaded] == [
        "guide.md",
        "legacy.htm",
        "notes.txt",
        "page.html",
    ]
    assert [item.media_type for item in loaded] == [
        "text/markdown",
        "text/html",
        "text/plain",
        "text/html",
    ]


def test_filesystem_loader_applies_include_and_exclude_globs(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    _ = (docs / "keep.md").write_text("keep", encoding="utf-8")
    _ = (docs / "keep.txt").write_text("keep", encoding="utf-8")
    _ = (docs / "skip.txt").write_text("skip", encoding="utf-8")

    loader = FileSystemLoader(
        include_globs=("**/*.md", "**/*.txt"),
        exclude_globs=("**/skip.txt",),
    )
    loaded = list(loader.load(tmp_path))

    assert [Path(item.source_path).name for item in loaded] == ["keep.md", "keep.txt"]


def test_filesystem_loader_skips_hidden_files_by_default(tmp_path: Path) -> None:
    _ = (tmp_path / ".hidden.md").write_text("hidden", encoding="utf-8")
    public_dir = tmp_path / "public"
    public_dir.mkdir()
    _ = (public_dir / "visible.md").write_text("visible", encoding="utf-8")

    loaded = list(FileSystemLoader().load(tmp_path))

    assert [Path(item.source_path).name for item in loaded] == ["visible.md"]


def test_filesystem_loader_can_include_hidden_files(tmp_path: Path) -> None:
    _ = (tmp_path / ".hidden.md").write_text("hidden", encoding="utf-8")

    loaded = list(FileSystemLoader(hidden_policy="include").load(tmp_path))

    assert [Path(item.source_path).name for item in loaded] == [".hidden.md"]


def test_filesystem_loader_skips_symlink_when_configured(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    _ = target.write_text("target", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(target)

    loaded = list(FileSystemLoader(symlink_policy="skip").load(tmp_path))

    assert [Path(item.source_path).name for item in loaded] == ["target.md"]


def test_filesystem_loader_follows_symlink_by_default(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    _ = target.write_text("target", encoding="utf-8")
    link = tmp_path / "link.md"
    link.symlink_to(target)

    loaded = list(FileSystemLoader().load(tmp_path))

    assert len(loaded) == 2
    assert [item.source_path for item in loaded] == [str(target.resolve()), str(target.resolve())]


def test_filesystem_loader_uses_stable_ordering_by_resolved_path(tmp_path: Path) -> None:
    _ = (tmp_path / "b.txt").write_text("B", encoding="utf-8")
    _ = (tmp_path / "a.md").write_text("A", encoding="utf-8")

    loaded = list(FileSystemLoader(include_globs=("**/*.md", "**/*.txt")).load(tmp_path))

    assert [Path(item.source_path).name for item in loaded] == ["a.md", "b.txt"]


def test_filesystem_loader_respects_encoding_error_policy(tmp_path: Path) -> None:
    path = tmp_path / "bytes.txt"
    path.write_bytes(b"hello\xff")

    with pytest.raises(LoadError, match="Failed to read"):
        _ = list(FileSystemLoader(include_globs=("**/*.txt",)).load(tmp_path))

    loaded = list(
        FileSystemLoader(include_globs=("**/*.txt",), encoding_errors="replace").load(tmp_path)
    )
    assert loaded[0].raw_text == "hello\ufffd"
