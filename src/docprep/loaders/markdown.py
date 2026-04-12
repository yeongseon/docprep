"""Markdown file loader."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from docprep.exceptions import LoadError
from docprep.ids import canonicalize_source_uri, sha256_checksum
from docprep.loaders.types import LoadedSource


class MarkdownLoader:
    """Loads Markdown files from a file or directory path."""

    def __init__(
        self,
        *,
        glob_pattern: str = "**/*.md",
        resolve_symlinks: bool = True,
    ) -> None:
        self._glob_pattern: str = glob_pattern
        self._resolve_symlinks: bool = resolve_symlinks

    def load(self, source: str | Path) -> Iterable[LoadedSource]:
        path = Path(source)
        if not path.exists():
            raise LoadError(f"Source path does not exist: {path}")

        if path.is_file():
            source_root = path.resolve().parent
            yield self._load_file(path, source_root)
        elif path.is_dir():
            yield from self._load_directory(path)
        else:
            raise LoadError(f"Source is neither a file nor directory: {path}")

    def _load_directory(self, directory: Path) -> Iterable[LoadedSource]:
        source_root = directory.resolve()
        files = sorted(directory.glob(self._glob_pattern))
        for file_path in files:
            if file_path.is_file():
                yield self._load_file(file_path, source_root)

    def _load_file(self, file_path: Path, source_root: Path) -> LoadedSource:
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise LoadError(f"Failed to read {file_path}: {exc}") from exc

        canonical_uri = canonicalize_source_uri(file_path, source_root=source_root)

        return LoadedSource(
            source_path=str(file_path.resolve() if self._resolve_symlinks else file_path),
            source_uri=canonical_uri,
            raw_text=raw_text,
            checksum=sha256_checksum(raw_text),
            media_type="text/markdown",
        )
