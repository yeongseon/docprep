from __future__ import annotations

from datetime import date

import pytest

from docprep.exceptions import MetadataError, ParseError
from docprep.ids import document_id
from docprep.loaders.types import LoadedSource
from docprep.parsers.markdown import MarkdownParser


def _loaded_source(raw_text: str, *, source_uri: str = "docs/example.md") -> LoadedSource:
    return LoadedSource(
        source_path=source_uri,
        source_uri=source_uri,
        raw_text=raw_text,
        checksum="checksum",
        source_metadata={"lang": "en"},
    )


def test_title_comes_from_frontmatter() -> None:
    doc = MarkdownParser().parse(_loaded_source("---\ntitle: Frontmatter\n---\n# Heading\n"))

    assert doc.title == "Frontmatter"


def test_title_comes_from_first_h1_when_frontmatter_has_no_title() -> None:
    doc = MarkdownParser().parse(_loaded_source("---\nfoo: bar\n---\n# Heading\nBody\n"))

    assert doc.title == "Heading"


def test_title_falls_back_to_filename_stem() -> None:
    doc = MarkdownParser().parse(_loaded_source("Body only", source_uri="docs/fallback-name.md"))

    assert doc.title == "fallback-name"


def test_frontmatter_is_extracted_correctly() -> None:
    doc = MarkdownParser().parse(_loaded_source("---\ntitle: Title\ntags:\n  - one\n---\nBody\n"))

    assert doc.frontmatter == {"title": "Title", "tags": ["one"]}


def test_body_markdown_excludes_frontmatter() -> None:
    doc = MarkdownParser().parse(_loaded_source("---\ntitle: Title\n---\nBody\n"))

    assert doc.body_markdown == "Body"


def test_document_id_is_deterministic_from_source_uri() -> None:
    source = _loaded_source("Body", source_uri="docs/item.md")

    assert MarkdownParser().parse(source).id == document_id(source.source_uri)


def test_parser_returns_document_with_empty_sections_and_chunks() -> None:
    doc = MarkdownParser().parse(_loaded_source("Body"))

    assert doc.sections == ()
    assert doc.chunks == ()
    assert doc.source_metadata == {"lang": "en"}


def test_frontmatter_date_values_are_normalized_to_iso_strings() -> None:
    doc = MarkdownParser().parse(_loaded_source("---\npublished: 2024-01-15\n---\nBody\n"))

    assert doc.frontmatter["published"] == "2024-01-15"


def test_parser_rejects_reserved_frontmatter_keys() -> None:
    with pytest.raises(MetadataError, match=r"frontmatter\.docprep\.source_uri"):
        _ = MarkdownParser().parse(_loaded_source("---\ndocprep.source_uri: hacked\n---\nBody\n"))


def test_source_metadata_date_values_are_normalized() -> None:
    source = LoadedSource(
        source_path="docs/example.md",
        source_uri="docs/example.md",
        raw_text="Body",
        checksum="checksum",
        source_metadata={"published": date(2024, 1, 15)},
    )

    doc = MarkdownParser().parse(source)

    assert doc.source_metadata == {"published": "2024-01-15"}


def test_parse_raises_for_invalid_frontmatter() -> None:
    source = _loaded_source("---\ntitle: [unterminated\n---\nBody\n")

    with pytest.raises(ParseError, match="Failed to parse frontmatter"):
        _ = MarkdownParser().parse(source)
