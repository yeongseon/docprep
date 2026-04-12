from __future__ import annotations

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker
from docprep.loaders.types import LoadedSource
from docprep.parsers.html import HtmlParser


def _loaded_source(raw_text: str, *, source_uri: str = "file:page.html") -> LoadedSource:
    return LoadedSource(
        source_path=source_uri,
        source_uri=source_uri,
        raw_text=raw_text,
        checksum="checksum",
        media_type="text/html",
    )


def test_html_parser_strips_script_style_and_noscript() -> None:
    raw = """
    <html><head><title>Doc</title><style>.x{display:none}</style></head>
    <body>
      <script>alert('x')</script>
      <noscript>fallback</noscript>
      <p>Visible</p>
    </body></html>
    """
    doc = HtmlParser().parse(_loaded_source(raw))

    assert doc.title == "Doc"
    assert "Visible" in doc.body_markdown
    assert "alert" not in doc.body_markdown
    assert "fallback" not in doc.body_markdown


def test_html_parser_extracts_title_from_h1_when_title_tag_missing() -> None:
    doc = HtmlParser().parse(_loaded_source("<body><h1>Main Heading</h1><p>Body</p></body>"))

    assert doc.title == "Main Heading"
    assert doc.body_markdown.startswith("# Main Heading")


def test_html_parser_decodes_entities_and_formats_lists_and_breaks() -> None:
    raw = "<p>A &amp; B<br>C</p><ul><li>One</li><li>Two</li></ul>"
    doc = HtmlParser().parse(_loaded_source(raw))

    assert "A & B\nC" in doc.body_markdown
    assert "- One" in doc.body_markdown
    assert "- Two" in doc.body_markdown


def test_html_parser_emits_fenced_code_blocks_for_pre_and_code() -> None:
    raw = "<pre><code>print('x')</code></pre><code>inline()</code>"
    doc = HtmlParser().parse(_loaded_source(raw))

    assert "```\nprint('x')\n```" in doc.body_markdown
    assert "```\ninline()\n```" in doc.body_markdown


def test_html_parser_handles_empty_html_and_falls_back_to_stem() -> None:
    doc = HtmlParser().parse(_loaded_source("", source_uri="file:docs/empty-page.html"))

    assert doc.title == "empty-page"
    assert doc.body_markdown == ""
    assert doc.source_type == "html"


def test_html_parser_handles_deeply_nested_content() -> None:
    raw = (
        "<div><section><article><p><span><strong>"
        "Nested text</strong></span></p></article></section></div>"
    )
    doc = HtmlParser().parse(_loaded_source(raw))

    assert "Nested text" in doc.body_markdown


def test_html_parser_output_works_with_existing_chunkers() -> None:
    raw = "<h1>Title</h1><p>Sentence one. Sentence two.</p>"
    parsed = HtmlParser().parse(_loaded_source(raw))
    sectioned = HeadingChunker().chunk(parsed)
    chunked = SizeChunker(max_chars=20).chunk(sectioned)

    assert len(sectioned.sections) == 1
    assert len(chunked.chunks) >= 1
