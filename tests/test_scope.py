from __future__ import annotations

from pathlib import Path

from docprep.models.domain import SourceScope
from docprep.scope import compute_stale_uris, derive_scope, uri_in_scope


def test_derive_scope_from_directory_path(tmp_path: Path) -> None:
    docs = tmp_path / "docs" / "api"
    docs.mkdir(parents=True)

    scope = derive_scope(docs, source_root=tmp_path)

    assert scope == SourceScope(prefixes=("file:docs/api/",), explicit=False)


def test_derive_scope_from_file_path(tmp_path: Path) -> None:
    file_path = tmp_path / "docs" / "api" / "guide.md"
    file_path.parent.mkdir(parents=True)
    _ = file_path.write_text("# Guide\n", encoding="utf-8")

    scope = derive_scope(file_path, source_root=tmp_path)

    assert scope == SourceScope(prefixes=("file:docs/api/guide.md",), explicit=False)


def test_derive_scope_uses_explicit_override() -> None:
    scope = derive_scope("ignored", explicit_scope="file:docs/reference/")

    assert scope == SourceScope(prefixes=("file:docs/reference/",), explicit=True)


def test_uri_in_scope_matches_directory_prefixes_and_files() -> None:
    directory_scope = SourceScope(prefixes=("file:docs/api/",))
    file_scope = SourceScope(prefixes=("file:docs/api/guide.md",))

    assert uri_in_scope("file:docs/api/guide.md", directory_scope)
    assert uri_in_scope("file:docs/api/nested/intro.md", directory_scope)
    assert not uri_in_scope("file:docs/reference/guide.md", directory_scope)
    assert uri_in_scope("file:docs/api/guide.md", file_scope)
    assert not uri_in_scope("file:docs/api/guide-v2.md", file_scope)


def test_uri_in_scope_root_file_prefix() -> None:
    scope = SourceScope(prefixes=("file:",), explicit=False)
    assert uri_in_scope("file:docs/foo.md", scope) is True
    assert uri_in_scope("file:README.md", scope) is True
    assert uri_in_scope("http://other", scope) is False


def test_compute_stale_uris_respects_scope_overlap_and_disjoint_sets() -> None:
    scope = SourceScope(prefixes=("file:docs/api/",))
    seen = {"file:docs/api/guide.md", "file:docs/api/new.md"}
    stored = {
        "file:docs/api/guide.md",
        "file:docs/api/old.md",
        "file:docs/reference/keep.md",
    }

    stale = compute_stale_uris(scope, seen_uris=seen, stored_uris=stored)

    assert stale == {"file:docs/api/old.md"}


def test_compute_stale_uris_with_empty_scope_prefixes() -> None:
    stale = compute_stale_uris(
        SourceScope(prefixes=()),
        seen_uris={"file:docs/api/guide.md"},
        stored_uris={"file:docs/api/guide.md", "file:docs/api/old.md"},
    )

    assert stale == set()


def test_scope_changes_between_runs_change_stale_candidates() -> None:
    stored = {
        "file:docs/api/guide.md",
        "file:docs/api/old.md",
        "file:docs/reference/keep.md",
    }
    seen = {"file:docs/api/guide.md"}

    api_stale = compute_stale_uris(
        SourceScope(prefixes=("file:docs/api/",)),
        seen_uris=seen,
        stored_uris=stored,
    )
    reference_stale = compute_stale_uris(
        SourceScope(prefixes=("file:docs/reference/",)),
        seen_uris=seen,
        stored_uris=stored,
    )

    assert api_stale == {"file:docs/api/old.md"}
    assert reference_stale == {"file:docs/reference/keep.md"}


def test_derive_scope_directory_without_source_root_matches_loader(tmp_path: Path) -> None:
    """When no source_root is given for a directory, scope should use the directory
    itself as root — consistent with FileSystemLoader which uses path.resolve().
    This produces scope 'file:' which matches all URIs from that directory."""
    docs = tmp_path / "docs"
    docs.mkdir()

    scope = derive_scope(docs)

    # Scope is 'file:' because the directory is its own root (same as loader)
    assert scope == SourceScope(prefixes=("file:",), explicit=False)


def test_same_file_produces_same_uri_from_different_roots(tmp_path: Path) -> None:
    """Same file produces deterministic URI regardless of invocation root."""
    # Create a nested file structure
    sub = tmp_path / "docs"
    sub.mkdir()
    f = sub / "guide.md"
    f.write_text("# Guide\n\nHello world\n")

    from docprep.ids import document_id
    from docprep.loaders.filesystem import FileSystemLoader

    loader = FileSystemLoader()

    # Load from directory (source_root = sub)
    dir_sources = list(loader.load(sub))
    # Load from file directly (source_root = sub.parent)
    file_sources = list(loader.load(f))

    assert len(dir_sources) == 1
    assert len(file_sources) == 1

    # Both should resolve to the same source_uri (deterministic identity)
    assert dir_sources[0].source_uri == file_sources[0].source_uri

    # Document IDs derived from URIs must also match
    assert document_id(dir_sources[0].source_uri) == document_id(file_sources[0].source_uri)


def test_files_in_different_directories_produce_distinct_uris(tmp_path: Path) -> None:
    """Files with the same name in different dirs produce distinct URIs.

    When loading multiple files from a common parent directory, same-named
    files in different subdirectories must produce distinct URIs.
    """
    # Create two subdirectories with identical filenames
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "readme.md").write_text("# A\n\nContent A\n")
    (dir_b / "readme.md").write_text("# B\n\nContent B\n")

    from docprep.ids import document_id
    from docprep.loaders.filesystem import FileSystemLoader

    loader = FileSystemLoader()
    # Load both files from the common parent directory
    sources = list(loader.load(tmp_path))

    assert len(sources) == 2, "Both readme.md files should be discovered"

    # Find sources by path to verify URIs
    source_a = next((s for s in sources if "a/readme.md" in s.source_path), None)
    source_b = next((s for s in sources if "b/readme.md" in s.source_path), None)

    assert source_a is not None, "readme.md in dir a should be found"
    assert source_b is not None, "readme.md in dir b should be found"

    # URIs must be distinct (no collision)
    assert source_a.source_uri != source_b.source_uri, (
        "Files in different directories must have distinct URIs"
    )

    # Document IDs (derived from URIs) must also be distinct
    assert document_id(source_a.source_uri) != document_id(source_b.source_uri), (
        "Document IDs must be distinct"
    )
