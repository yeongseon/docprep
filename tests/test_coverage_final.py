from __future__ import annotations

from collections.abc import Iterable, Iterator
import importlib
from pathlib import Path
import time
from typing import cast
import uuid

import pytest

from docprep.config import TokenChunkerConfig, load_config
from docprep.exceptions import ConfigError, IngestError, ParseError
from docprep.ingest import Ingestor, _parse_and_chunk
from docprep.loaders.types import LoadedSource
from docprep.models.domain import Document, DocumentError, ErrorMode, PipelineStage, Section
from docprep.parsers.html import HtmlParser, _HtmlToMarkdownParser
from docprep.parsers.rst import RstParser
import docprep.registry as registry

PARSER_GROUP = cast(str, getattr(registry, "PARSER_GROUP", "docprep.parsers"))
ADAPTER_GROUP = cast(str, getattr(registry, "ADAPTER_GROUP", "docprep.adapters"))

ingest_module = importlib.import_module("docprep.ingest")


def _loaded_source(source_uri: str, raw_text: str) -> LoadedSource:
    return LoadedSource(
        source_path=source_uri, source_uri=source_uri, raw_text=raw_text, checksum=source_uri
    )


def _document(source_uri: str, checksum: str) -> Document:
    return Document(
        id=uuid.uuid4(),
        source_uri=source_uri,
        title=Path(source_uri).stem,
        source_checksum=checksum,
    )


def _write_toml(tmp_path: Path, content: str, *, name: str = "docprep.toml") -> Path:
    path = tmp_path / name
    _ = path.write_text(content, encoding="utf-8")
    return path


def test_html_parser_covers_ignored_depth_and_inline_newline_paths() -> None:
    raw = """
    <script><div>ignored</div><span>still ignored</span></script>
    <h2>Head<br>Line</h2>
    <pre>a<br>b</pre>
    <li>one<br>two</li>
    free<br>text
    """
    doc = HtmlParser().parse(_loaded_source("file:test.html", raw))

    assert "ignored" not in doc.body_markdown
    assert "## Head\nLine" in doc.body_markdown
    assert "```\na\nb\n```" in doc.body_markdown
    assert "- one\ntwo" in doc.body_markdown
    assert "free\ntext" in doc.body_markdown


def test_html_parser_covers_free_text_and_table_edge_helpers() -> None:
    parser = _HtmlToMarkdownParser()
    parser.feed("bare text")
    parser.close()

    assert parser.blocks == ["bare text"]
    assert parser._table_to_markdown([]) == ""
    assert parser._table_to_markdown([[]]) == ""
    assert parser._table_to_markdown([["A", "B"], ["1"]]).splitlines()[-1] == "| 1 |  |"

    empty_block_parser = _HtmlToMarkdownParser()
    empty_block_parser._append_block("")
    assert empty_block_parser.blocks == []


def test_html_parser_wraps_internal_parser_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(self: _HtmlToMarkdownParser, data: str) -> None:
        del self
        del data
        raise RuntimeError("bad html")

    monkeypatch.setattr(_HtmlToMarkdownParser, "feed", _boom)

    with pytest.raises(ParseError, match="Failed to parse HTML"):
        _ = HtmlParser().parse(_loaded_source("file:broken.html", "<p>x</p>"))


@pytest.mark.parametrize(
    ("name", "content", "match"),
    [
        (
            "hidden-policy.toml",
            "[loader]\ntype = 'filesystem'\nhidden_policy = 'bad'\n",
            "loader.hidden_policy",
        ),
        (
            "symlink-policy.toml",
            "[loader]\ntype = 'filesystem'\nsymlink_policy = 'bad'\n",
            "loader.symlink_policy",
        ),
        (
            "encoding.toml",
            "[loader]\ntype = 'filesystem'\nencoding = 123\n",
            "loader.encoding: expected string",
        ),
        (
            "encoding-errors.toml",
            "[loader]\ntype = 'filesystem'\nencoding_errors = 'bad'\n",
            "loader.encoding_errors",
        ),
        (
            "include-globs.toml",
            "[loader]\ntype = 'filesystem'\ninclude_globs = [123]\n",
            r"loader\.include_globs\[0\]: expected string",
        ),
        (
            "tokenizer.toml",
            "[[chunkers]]\ntype = 'token'\ntokenizer = 123\n",
            r"chunkers\[0\]\.tokenizer: expected string",
        ),
        (
            "export-table.toml",
            "export = 'bad'\n",
            "export: expected table",
        ),
        (
            "export-type.toml",
            "[export]\ntext_prepend = 123\n",
            "export.text_prepend: expected string",
        ),
        (
            "non-string-type.toml",
            "[parser]\ntype = 123\n",
            "parser.type: expected string",
        ),
    ],
)
def test_config_validation_error_paths(tmp_path: Path, name: str, content: str, match: str) -> None:
    path = _write_toml(tmp_path, content, name=name)
    with pytest.raises(ConfigError, match=match):
        _ = load_config(path)


def test_rst_parser_field_list_with_leading_blank_lines_and_non_field_lines() -> None:
    raw = "\n\n:Title: Metadata title\n:not_a_field\n\nHeading\n=======\n"
    doc = RstParser().parse(_loaded_source("docs/example.rst", raw))

    assert doc.frontmatter["Title"] == "Metadata title"
    assert doc.title == "Metadata title"
    assert "# Heading" in doc.body_markdown


def test_registry_private_and_plugin_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    assert registry.BUILTIN_PARSERS == dict(registry.BUILTIN_PARSERS)
    expected_without_rst = {
        name: parser for name, parser in registry.BUILTIN_PARSERS.items() if name != "rst"
    }
    assert registry.BUILTIN_PARSERS == expected_without_rst

    with pytest.raises(ValueError, match="Invalid object path"):
        _ = registry._load_object_path("not-a-path")

    assert "markdown" in registry._builtin_components(PARSER_GROUP)
    assert registry._builtin_components(ADAPTER_GROUP) == {}

    monkeypatch.setattr(
        registry,
        "discover_entry_points",
        lambda group: {"adapter": object()} if group == ADAPTER_GROUP else {},
    )
    assert "adapter" in registry.get_all_adapters()


def test_registry_whitespace_token_counter_branch() -> None:
    chunker = registry.build_chunker(
        TokenChunkerConfig(max_tokens=2, overlap_tokens=1, tokenizer="whitespace")
    )
    doc = Document(
        id=uuid.uuid4(),
        source_uri="docs/tokens.md",
        title="tokens",
        source_checksum="checksum",
        sections=(
            Section(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                order_index=0,
                content_markdown="one two three",
            ),
        ),
    )
    chunked = chunker.chunk(doc)
    assert [chunk.content_text for chunk in chunked.chunks] == ["one two", "two three"]


def test_parse_and_chunk_returns_chunk_failure() -> None:
    loaded = _loaded_source("docs/chunk-fail.md", "body")

    class OkParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document(loaded_source.source_uri, loaded_source.checksum)

    class FailingChunker:
        def chunk(self, document: Document) -> Document:
            raise RuntimeError(f"chunk boom: {document.source_uri}")

    result = _parse_and_chunk(0, loaded, OkParser(), [FailingChunker()])
    assert isinstance(result, ingest_module._ParseChunkFailure)
    assert result.errors[0].stage == PipelineStage.CHUNK


def test_ingestor_rejects_workers_less_than_one(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n", encoding="utf-8")

    with pytest.raises(IngestError, match="workers must be >= 1"):
        _ = Ingestor().run(path, workers=0)


def test_ingestor_parallel_future_exception_path(monkeypatch: pytest.MonkeyPatch) -> None:
    sources = [
        _loaded_source("docs/fail.md", "x"),
        _loaded_source("docs/ok.md", "x"),
    ]

    class Loader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return sources

    def _patched_parse_and_chunk(
        index: int, loaded_source: LoadedSource, parser: object, chunkers: object
    ) -> object:
        del parser
        del chunkers
        if loaded_source.source_uri == "docs/fail.md":
            raise RuntimeError("future boom")
        return ingest_module._ParseChunkSuccess(
            index=index,
            document=_document(loaded_source.source_uri, loaded_source.checksum),
            parse_elapsed_ms=0.0,
            chunk_elapsed_ms=0.0,
        )

    monkeypatch.setattr(ingest_module, "_parse_and_chunk", _patched_parse_and_chunk)

    result = Ingestor(loader=Loader(), parser=None, chunkers=[]).run("ignored", workers=2)
    assert result.processed_count == 1
    assert result.failed_count == 1
    assert result.failed_source_uris == ("docs/fail.md",)


def test_ingestor_fail_fast_cancels_pending_futures_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    sources = [
        _loaded_source("docs/fail-first.md", "x"),
        _loaded_source("docs/slow.md", "x"),
    ]

    class Loader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return sources

    def _patched_parse_and_chunk(
        index: int, loaded_source: LoadedSource, parser: object, chunkers: object
    ) -> object:
        del parser
        del chunkers
        if index == 0:
            return ingest_module._ParseChunkFailure(
                index=index,
                source_uri=loaded_source.source_uri,
                errors=[
                    DocumentError(
                        source_uri=loaded_source.source_uri,
                        stage=PipelineStage.PARSE,
                        error_type="RuntimeError",
                        message="planned parse failure",
                    )
                ],
                parse_elapsed_ms=0.0,
                chunk_elapsed_ms=0.0,
            )
        time.sleep(0.05)
        return ingest_module._ParseChunkSuccess(
            index=index,
            document=_document(loaded_source.source_uri, loaded_source.checksum),
            parse_elapsed_ms=0.0,
            chunk_elapsed_ms=0.0,
        )

    def _first_only(futures: Iterable[object]) -> Iterator[object]:
        future_list = list(futures)
        if future_list:
            yield future_list[0]

    monkeypatch.setattr(ingest_module, "_parse_and_chunk", _patched_parse_and_chunk)
    monkeypatch.setattr(ingest_module.concurrent.futures, "as_completed", _first_only)

    with pytest.raises(IngestError, match="parse failed for docs/fail-first.md"):
        _ = Ingestor(
            loader=Loader(),
            parser=None,
            chunkers=[],
            error_mode=ErrorMode.FAIL_FAST,
        ).run("ignored", workers=2)
