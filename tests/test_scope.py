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
