from __future__ import annotations

import os
from pathlib import Path

import pytest

from docprep.ids import canonicalize_source_uri, document_id
from docprep.ingest import Ingestor


def test_canonicalize_relative_path_under_source_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    file_path = docs / "guide.md"
    _ = file_path.write_text("# Guide\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    uri = canonicalize_source_uri("docs/guide.md", source_root="docs")

    assert uri == "file:guide.md"


def test_canonicalize_dot_prefix_matches_plain_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    file_path = docs / "guide.md"
    _ = file_path.write_text("# Guide\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    with_dot = canonicalize_source_uri("./docs/guide.md", source_root="./docs")
    plain = canonicalize_source_uri("docs/guide.md", source_root="docs")

    assert with_dot == plain == "file:guide.md"


def test_canonicalize_absolute_path_relative_to_source_root(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    file_path = docs / "guide.md"
    _ = file_path.write_text("# Guide\n", encoding="utf-8")

    uri = canonicalize_source_uri(file_path.resolve(), source_root=docs.resolve())

    assert uri == "file:guide.md"


def test_canonicalize_nested_path_with_trailing_slash_root(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    nested = docs / "sub"
    nested.mkdir(parents=True)
    file_path = nested / "nested.md"
    _ = file_path.write_text("# Nested\n", encoding="utf-8")

    uri = canonicalize_source_uri(file_path, source_root=f"{docs}/")

    assert uri == "file:sub/nested.md"


def test_canonicalize_file_outside_source_root_falls_back_to_absolute(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    outside = tmp_path / "outside.md"
    _ = outside.write_text("# Outside\n", encoding="utf-8")

    uri = canonicalize_source_uri(outside, source_root=docs)

    assert uri == f"file:{outside.resolve().as_posix()}"


def test_canonicalize_resolves_symlink_to_real_path(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    real_file = real_dir / "guide.md"
    _ = real_file.write_text("# Guide\n", encoding="utf-8")
    symlink = docs / "guide.md"
    symlink.symlink_to(real_file)

    symlink_uri = canonicalize_source_uri(symlink, source_root=docs)
    real_uri = canonicalize_source_uri(real_file, source_root=docs)

    assert symlink_uri == real_uri == f"file:{real_file.resolve().as_posix()}"


def test_same_file_path_variants_produce_same_uri_and_document_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    file_path = docs / "guide.md"
    _ = file_path.write_text("# Guide\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    rel = canonicalize_source_uri("docs/guide.md", source_root="docs")
    dot_rel = canonicalize_source_uri("./docs/guide.md", source_root="./docs")
    abs_rel = canonicalize_source_uri(file_path.resolve(), source_root=docs.resolve())

    assert rel == dot_rel == abs_rel == "file:guide.md"
    assert document_id(rel) == document_id(dot_rel) == document_id(abs_rel)


def test_case_variants_canonicalize_identically_on_case_insensitive_filesystems(
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        pytest.skip("Case-insensitive path variant behavior is Windows-specific")

    docs = tmp_path / "docs"
    docs.mkdir()
    file_path = docs / "guide.md"
    _ = file_path.write_text("# Guide\n", encoding="utf-8")

    lower = canonicalize_source_uri(str(file_path), source_root=str(docs))
    upper = canonicalize_source_uri(str(file_path).upper(), source_root=str(docs).upper())

    assert lower == upper == "file:guide.md"


def test_ingestor_emits_canonical_file_uris(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    nested = docs / "sub"
    nested.mkdir(parents=True)
    file_path = nested / "nested.md"
    _ = file_path.write_text("# Nested\n\nBody\n", encoding="utf-8")

    result = Ingestor().run(docs)

    assert len(result.documents) == 1
    assert result.documents[0].source_uri == "file:sub/nested.md"
    assert result.documents[0].source_uri.startswith("file:")
