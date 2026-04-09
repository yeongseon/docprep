"""Markdown file loader."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from docprep.exceptions import LoadError
from docprep.ids import sha256_checksum
from docprep.loaders.types import LoadedSource


class MarkdownLoader:
    """Loads Markdown files from a file or directory path."""

    def __init__(self, *, glob_pattern: str = "**/*.md") -> None:
        self._glob_pattern = glob_pattern

    def load(self, source: str | Path) -> Iterable[LoadedSource]:
        path = Path(source)
        if not path.exists():
            raise LoadError(f"Source path does not exist: {path}")

        if path.is_file():
            yield self._load_file(path)
        elif path.is_dir():
            yield from self._load_directory(path)
        else:
            raise LoadError(f"Source is neither a file nor directory: {path}")

    def _load_directory(self, directory: Path) -> Iterable[LoadedSource]:
        files = sorted(directory.glob(self._glob_pattern))
        for file_path in files:
            if file_path.is_file():
                yield self._load_file(file_path)

    def _load_file(self, file_path: Path) -> LoadedSource:
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise LoadError(f"Failed to read {file_path}: {exc}") from exc

        return LoadedSource(
            source_path=str(file_path),
            source_uri=file_path.as_posix(),
            raw_text=raw_text,
            checksum=sha256_checksum(raw_text),
            media_type="text/markdown",
        )
