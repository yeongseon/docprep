from __future__ import annotations

from pathlib import Path

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker
from docprep.loaders.types import LoadedSource
from docprep.parsers.plaintext import PlainTextParser


def _loaded_source(raw_text: str, *, source_uri: str = "file:notes.txt") -> LoadedSource:
    return LoadedSource(
        source_path=source_uri,
        source_uri=source_uri,
        raw_text=raw_text,
        checksum="checksum",
        media_type="text/plain",
    )


def test_plaintext_parser_uses_first_non_empty_line_as_title() -> None:
    doc = PlainTextParser().parse(_loaded_source("\n\nFirst title\nSecond line\n"))

    assert doc.title == "First title"
    assert doc.source_type == "plaintext"
    assert doc.body_markdown == "\n\nFirst title\nSecond line\n"


def test_plaintext_parser_falls_back_to_file_stem_for_empty_content() -> None:
    doc = PlainTextParser().parse(_loaded_source("\n\n", source_uri="file:docs/empty-note.txt"))

    assert doc.title == "empty-note"
    assert doc.frontmatter == {}
    assert doc.source_metadata == {}


def test_plaintext_parser_body_flows_through_existing_chunkers() -> None:
    parsed = PlainTextParser().parse(_loaded_source("Alpha line\nBeta line\nGamma line"))
    sectioned = HeadingChunker().chunk(parsed)
    chunked = SizeChunker(max_chars=20).chunk(sectioned)

    assert len(chunked.sections) == 1
    assert len(chunked.chunks) >= 1
    assert all(chunk.content_text for chunk in chunked.chunks)


def test_plaintext_parser_title_fallback_supports_non_file_uri() -> None:
    doc = PlainTextParser().parse(_loaded_source("", source_uri="docs/readme.txt"))

    assert doc.title == Path("docs/readme.txt").stem


def test_plaintext_parser_preserves_source_metadata() -> None:
    source = LoadedSource(
        source_path="file:notes.txt",
        source_uri="file:notes.txt",
        raw_text="Content",
        checksum="checksum",
        media_type="text/plain",
        source_metadata={"lang": "en", "author": "Alice"},
    )
    doc = PlainTextParser().parse(source)

    assert doc.source_metadata == {"lang": "en", "author": "Alice"}
