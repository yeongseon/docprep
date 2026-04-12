from __future__ import annotations

import pytest

from docprep.exceptions import ParseError
from docprep.loaders.types import LoadedSource
from docprep.parsers.multi import MultiFormatParser


def _loaded_source(media_type: str, raw_text: str, source_uri: str) -> LoadedSource:
    return LoadedSource(
        source_path=source_uri,
        source_uri=source_uri,
        raw_text=raw_text,
        checksum="checksum",
        media_type=media_type,
    )


def test_multi_parser_dispatches_by_media_type() -> None:
    parser = MultiFormatParser()

    markdown_doc = parser.parse(_loaded_source("text/markdown", "# Title\n\nBody\n", "file:doc.md"))
    text_doc = parser.parse(_loaded_source("text/plain", "Line one\n", "file:doc.txt"))
    html_doc = parser.parse(_loaded_source("text/html", "<h1>Heading</h1>", "file:doc.html"))

    assert markdown_doc.source_type == "markdown"
    assert text_doc.source_type == "plaintext"
    assert html_doc.source_type == "html"


def test_multi_parser_raises_for_unknown_media_type() -> None:
    parser = MultiFormatParser()

    with pytest.raises(ParseError, match="No parser for media type"):
        _ = parser.parse(_loaded_source("application/json", "{}", "file:data.json"))
