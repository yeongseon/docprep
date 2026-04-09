from __future__ import annotations

from docprep.loaders.types import LoadedSource


def test_loaded_source_creation_with_required_fields() -> None:
    source = LoadedSource(
        source_path="/tmp/file.md",
        source_uri="/tmp/file.md",
        raw_text="# Title",
        checksum="checksum",
    )

    assert source.media_type == "text/markdown"
    assert source.source_metadata == {}


def test_loaded_source_creation_with_optional_fields() -> None:
    source = LoadedSource(
        source_path="/tmp/file.md",
        source_uri="/tmp/file.md",
        raw_text="# Title",
        checksum="checksum",
        media_type="text/plain",
        source_metadata={"lang": "en"},
    )

    assert source.media_type == "text/plain"
    assert source.source_metadata == {"lang": "en"}
