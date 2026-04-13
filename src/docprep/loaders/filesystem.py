from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Literal

from ..exceptions import LoadError
from ..ids import canonicalize_source_uri, sha256_checksum
from .types import MEDIA_TYPE_BY_SUFFIX, LoadedSource


class FileSystemLoader:
    def __init__(
        self,
        *,
        include_globs: Sequence[str] = ("**/*.md", "**/*.txt", "**/*.html", "**/*.htm", "**/*.rst"),
        exclude_globs: Sequence[str] = (),
        hidden_policy: Literal["skip", "include"] = "skip",
        symlink_policy: Literal["follow", "skip"] = "follow",
        encoding: str = "utf-8",
        encoding_errors: str = "strict",
    ) -> None:
        self._include_globs = tuple(include_globs)
        self._exclude_globs = tuple(exclude_globs)
        self._hidden_policy = hidden_policy
        self._symlink_policy = symlink_policy
        self._encoding = encoding
        self._encoding_errors = encoding_errors

    def load(self, source: str | Path) -> Iterable[LoadedSource]:
        path = Path(source)
        if not path.exists():
            raise LoadError(f"Source path does not exist: {path}")

        if path.is_file():
            source_root = path.resolve().parent
            if self._should_load(path, source_root):
                yield self._load_file(path, source_root)
            return

        if path.is_dir():
            source_root = path.resolve()
            for file_path in self._discover_files(path):
                yield self._load_file(file_path, source_root)
            return

        raise LoadError(f"Source is neither a file nor directory: {path}")

    def _discover_files(self, directory: Path) -> list[Path]:
        included: set[Path] = set()
        for pattern in self._include_globs:
            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    included.add(file_path)

        excluded: set[Path] = set()
        for pattern in self._exclude_globs:
            for file_path in directory.glob(pattern):
                if file_path.is_file():
                    excluded.add(file_path)

        source_root = directory.resolve()
        filtered = [
            file_path
            for file_path in included
            if file_path not in excluded and self._should_load(file_path, source_root)
        ]

        return sorted(filtered, key=lambda file_path: str(file_path.resolve()))

    def _should_load(self, file_path: Path, source_root: Path) -> bool:
        if self._hidden_policy == "skip" and self._is_hidden(file_path, source_root):
            return False
        if self._symlink_policy == "skip" and self._has_symlink_component(file_path, source_root):
            return False
        return True

    def _is_hidden(self, file_path: Path, source_root: Path) -> bool:
        try:
            rel_parts = file_path.resolve().relative_to(source_root).parts
        except ValueError:
            rel_parts = file_path.parts
        return any(part.startswith(".") for part in rel_parts)

    def _has_symlink_component(self, file_path: Path, source_root: Path) -> bool:
        try:
            rel_path = file_path.relative_to(source_root)
        except ValueError:
            return file_path.is_symlink()

        current = source_root
        for part in rel_path.parts:
            current = current / part
            if current.is_symlink():
                return True
        return False

    def _load_file(self, file_path: Path, source_root: Path) -> LoadedSource:
        suffix = file_path.suffix.lower()
        media_type = MEDIA_TYPE_BY_SUFFIX.get(suffix)
        if media_type is None:
            raise LoadError(f"Unsupported file extension for {file_path}")

        try:
            raw_text = file_path.read_text(encoding=self._encoding, errors=self._encoding_errors)
        except (OSError, UnicodeDecodeError) as exc:
            raise LoadError(f"Failed to read {file_path}: {exc}") from exc

        resolved_path = file_path.resolve()
        canonical_uri = canonicalize_source_uri(
            resolved_path if self._symlink_policy == "follow" else file_path,
            source_root=source_root,
        )

        return LoadedSource(
            source_path=str(resolved_path if self._symlink_policy == "follow" else file_path),
            source_uri=canonical_uri,
            raw_text=raw_text,
            checksum=sha256_checksum(raw_text),
            media_type=media_type,
        )
