from __future__ import annotations

from pathlib import Path

from docprep.config import RstParserConfig, load_config
from docprep.loaders.filesystem import FileSystemLoader
from docprep.loaders.types import LoadedSource
from docprep.parsers.multi import MultiFormatParser
from docprep.parsers.rst import RstParser
from docprep.registry import BUILTIN_PARSERS, build_parser


def _loaded_source(raw_text: str, *, source_uri: str = "docs/example.rst") -> LoadedSource:
    return LoadedSource(
        source_path=source_uri,
        source_uri=source_uri,
        raw_text=raw_text,
        checksum="checksum",
        media_type="text/x-rst",
    )


def test_rst_headings_are_converted_to_markdown_hierarchy() -> None:
    raw = """Main Title
==========

Subtitle
--------

Paragraph.
"""
    doc = RstParser().parse(_loaded_source(raw))

    assert doc.title == "Main Title"
    assert doc.body_markdown == "# Main Title\n\n## Subtitle\n\nParagraph."
    assert doc.source_type == "rst"


def test_rst_field_list_is_extracted_as_frontmatter() -> None:
    raw = """:Author: John Doe
:Date: 2024-01-01
:Version: 1.0

Heading
=======
"""
    doc = RstParser().parse(_loaded_source(raw))

    assert doc.frontmatter == {"Author": "John Doe", "Date": "2024-01-01", "Version": "1.0"}
    assert doc.body_markdown == "# Heading"


def test_rst_title_priority_prefers_field_list_title() -> None:
    raw = """:title: Metadata Title

Heading
=======
"""
    doc = RstParser().parse(_loaded_source(raw, source_uri="docs/title-priority.rst"))

    assert doc.title == "Metadata Title"


def test_rst_title_falls_back_to_filename_stem_when_no_heading() -> None:
    doc = RstParser().parse(_loaded_source("Body only", source_uri="docs/fallback-name.rst"))

    assert doc.title == "fallback-name"


def test_rst_multiple_adornment_styles_map_to_incrementing_levels() -> None:
    raw = """Top
===

Middle
------

Low
~~~
"""
    doc = RstParser().parse(_loaded_source(raw))

    assert doc.body_markdown == "# Top\n\n## Middle\n\n### Low"


def test_rst_overline_and_underline_heading_is_supported() -> None:
    raw = """============
Overlined
============

Body
"""
    doc = RstParser().parse(_loaded_source(raw))

    assert doc.title == "Overlined"
    assert doc.body_markdown == "# Overlined\n\nBody"


def test_rst_empty_document_returns_empty_body_and_stem_title() -> None:
    doc = RstParser().parse(_loaded_source("", source_uri="file:docs/empty.rst"))

    assert doc.title == "empty"
    assert doc.body_markdown == ""
    assert doc.frontmatter == {}


def test_rst_field_list_value_can_contain_colon() -> None:
    raw = """:Date: 2024-01-01T12:30:00Z

Title
=====
"""
    doc = RstParser().parse(_loaded_source(raw))

    assert doc.frontmatter == {"Date": "2024-01-01T12:30:00Z"}


def test_rst_field_list_can_precede_headings() -> None:
    raw = """:Author: Jane

Section
=======

Body
"""
    doc = RstParser().parse(_loaded_source(raw))

    assert doc.frontmatter == {"Author": "Jane"}
    assert doc.body_markdown.startswith("# Section")


def test_filesystem_loader_and_multi_parser_support_rst_integration(tmp_path: Path) -> None:
    rst_path = tmp_path / "guide.rst"
    _ = rst_path.write_text("Heading\n=======\n\nContent\n", encoding="utf-8")

    loaded = list(FileSystemLoader().load(tmp_path))

    assert len(loaded) == 1
    assert loaded[0].media_type == "text/x-rst"
    parsed = MultiFormatParser().parse(loaded[0])
    assert parsed.source_type == "rst"
    assert parsed.body_markdown == "# Heading\n\nContent"


def test_config_registry_and_builder_support_rst_parser(tmp_path: Path) -> None:
    config_path = tmp_path / "docprep.toml"
    _ = config_path.write_text("[parser]\ntype = 'rst'\n", encoding="utf-8")

    config = load_config(config_path)

    assert config.parser == RstParserConfig()
    assert "rst" in BUILTIN_PARSERS
    assert build_parser(RstParserConfig()).__class__ is RstParser


def test_rst_preserves_source_metadata() -> None:
    source = LoadedSource(
        source_path="docs/example.rst",
        source_uri="docs/example.rst",
        raw_text="Heading\n=======\n\nBody",
        checksum="checksum",
        media_type="text/x-rst",
        source_metadata={"lang": "en", "author": "Charlie"},
    )
    doc = RstParser().parse(source)

    assert doc.source_metadata == {"lang": "en", "author": "Charlie"}
