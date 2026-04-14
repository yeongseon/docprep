from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, cast
from unittest.mock import patch
import uuid

import pytest

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker
from docprep.chunkers.token import TokenChunker
from docprep.config import (
    AutoParserConfig,
    FileSystemLoaderConfig,
    HeadingChunkerConfig,
    HtmlParserConfig,
    MarkdownLoaderConfig,
    MarkdownParserConfig,
    PlainTextParserConfig,
    SizeChunkerConfig,
    SQLAlchemySinkConfig,
    TokenChunkerConfig,
)
from docprep.loaders.filesystem import FileSystemLoader
from docprep.loaders.markdown import MarkdownLoader
from docprep.models.domain import Document, Section
from docprep.parsers.html import HtmlParser
from docprep.parsers.markdown import MarkdownParser
from docprep.parsers.multi import MultiFormatParser
from docprep.parsers.plaintext import PlainTextParser
from docprep.registry import (
    BUILTIN_CHUNKERS,
    BUILTIN_LOADERS,
    BUILTIN_PARSERS,
    BUILTIN_SINKS,
    build_chunker,
    build_chunkers,
    build_loader,
    build_parser,
    build_sink,
)
from docprep.sinks.sqlalchemy import SQLAlchemySink


def test_builtin_registry_dicts_expose_expected_components() -> None:
    assert BUILTIN_LOADERS == {"markdown": MarkdownLoader, "filesystem": FileSystemLoader}
    assert BUILTIN_PARSERS == {
        "markdown": MarkdownParser,
        "plaintext": PlainTextParser,
        "html": HtmlParser,
        "auto": MultiFormatParser,
    }
    assert BUILTIN_CHUNKERS == {
        "heading": HeadingChunker,
        "size": SizeChunker,
        "token": TokenChunker,
    }
    assert BUILTIN_SINKS == {"sqlalchemy": "docprep.sinks.sqlalchemy.SQLAlchemySink"}


def test_build_loader_returns_markdown_loader_with_configured_glob_pattern(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    guide = docs_dir / "guide.md"
    notes = tmp_path / "notes.md"
    _ = guide.write_text("# Guide\n", encoding="utf-8")
    _ = notes.write_text("# Notes\n", encoding="utf-8")
    loader = build_loader(MarkdownLoaderConfig(glob_pattern="docs/*.md"))

    assert isinstance(loader, MarkdownLoader)

    loaded = list(loader.load(tmp_path))

    assert [Path(item.source_path) for item in loaded] == [guide]


def test_build_parser_returns_markdown_parser() -> None:
    parser = build_parser(MarkdownParserConfig())

    assert isinstance(parser, MarkdownParser)


def test_build_loader_returns_filesystem_loader_for_filesystem_config() -> None:
    loader = build_loader(FileSystemLoaderConfig(include_globs=("**/*.txt",)))

    assert isinstance(loader, FileSystemLoader)


def test_build_parser_supports_all_parser_config_types() -> None:
    assert isinstance(build_parser(PlainTextParserConfig()), PlainTextParser)
    assert isinstance(build_parser(HtmlParserConfig()), HtmlParser)
    assert isinstance(build_parser(AutoParserConfig()), MultiFormatParser)


def test_build_chunker_returns_heading_chunker_for_heading_config() -> None:
    chunker = build_chunker(HeadingChunkerConfig())

    assert isinstance(chunker, HeadingChunker)


def test_build_chunker_returns_size_chunker_for_size_config() -> None:
    chunker = build_chunker(SizeChunkerConfig(max_chars=42))
    document = Document(
        id=uuid.uuid4(),
        source_uri="guide.md",
        title="Guide",
        source_checksum="checksum",
        sections=(
            Section(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                order_index=0,
                content_markdown="A" * 50,
            ),
        ),
    )

    assert isinstance(chunker, SizeChunker)
    assert len(chunker.chunk(document).chunks) == 2


def test_build_chunkers_returns_tuple_of_chunkers_in_order() -> None:
    chunkers = build_chunkers((HeadingChunkerConfig(), SizeChunkerConfig(max_chars=33)))
    parsed = Document(
        id=uuid.uuid4(),
        source_uri="guide.md",
        title="Guide",
        source_checksum="checksum",
        body_markdown="# Title\n\n" + ("A" * 40),
    )

    assert isinstance(chunkers, tuple)
    assert [type(chunker) for chunker in chunkers] == [HeadingChunker, SizeChunker]
    chunked = chunkers[1].chunk(chunkers[0].chunk(parsed))
    assert len(chunked.chunks) == 2


def test_build_chunker_returns_token_chunker_for_token_config() -> None:
    chunker = build_chunker(
        TokenChunkerConfig(max_tokens=2, overlap_tokens=1, tokenizer="character")
    )
    document = Document(
        id=uuid.uuid4(),
        source_uri="guide.md",
        title="Guide",
        source_checksum="checksum",
        sections=(
            Section(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                order_index=0,
                content_markdown="abcd",
            ),
        ),
    )

    assert isinstance(chunker, TokenChunker)
    assert [chunk.content_text for chunk in chunker.chunk(document).chunks] == ["ab", "bcd"]


def test_build_sink_returns_sqlalchemy_sink_with_created_engine() -> None:
    sink = cast(
        SQLAlchemySink,
        build_sink(SQLAlchemySinkConfig(database_url="sqlite://", create_tables=True)),
    )
    stats = sink.stats()

    assert isinstance(sink, SQLAlchemySink)
    assert (stats.documents, stats.sections, stats.chunks) == (0, 0, 0)


def test_builders_fall_back_to_plugin_constructors_with_config_kwargs() -> None:
    class CustomLoader:
        def __init__(self, *, glob_pattern: str, include_hidden: bool):
            self.glob_pattern = glob_pattern
            self.include_hidden = include_hidden

    class CustomParser:
        def __init__(self, *, mode: str):
            self.mode = mode

    class CustomChunker:
        def __init__(self, *, max_sentences: int):
            self.max_sentences = max_sentences

    class CustomSink:
        def __init__(self, *, endpoint: str, timeout_seconds: int):
            self.endpoint = endpoint
            self.timeout_seconds = timeout_seconds

    def _discover(group: str) -> dict[str, object]:
        if group == "docprep.loaders":
            return {"my_custom_loader": CustomLoader}
        if group == "docprep.parsers":
            return {"my_custom_parser": CustomParser}
        if group == "docprep.chunkers":
            return {"my_custom_chunker": CustomChunker}
        if group == "docprep.sinks":
            return {"my_custom_sink": CustomSink}
        return {}

    with patch("docprep.registry.discover_entry_points", side_effect=_discover):
        loader = build_loader(
            cast(
                object,
                SimpleNamespace(
                    type="my_custom_loader", glob_pattern="**/*.md", include_hidden=True
                ),
            )
        )
        parser = build_parser(cast(object, SimpleNamespace(type="my_custom_parser", mode="strict")))
        chunker = build_chunker(
            cast(object, SimpleNamespace(type="my_custom_chunker", max_sentences=3))
        )
        sink = build_sink(
            cast(
                object,
                SimpleNamespace(
                    type="my_custom_sink", endpoint="https://sink.local", timeout_seconds=10
                ),
            )
        )

    assert isinstance(loader, CustomLoader)
    assert loader.glob_pattern == "**/*.md"
    assert loader.include_hidden is True
    assert isinstance(parser, CustomParser)
    assert parser.mode == "strict"
    assert isinstance(chunker, CustomChunker)
    assert chunker.max_sentences == 3
    assert isinstance(sink, CustomSink)
    assert sink.endpoint == "https://sink.local"
    assert sink.timeout_seconds == 10


@dataclass(slots=True)
class _UnknownComponentConfig:
    type: str


@pytest.mark.parametrize(
    ("builder", "config", "group"),
    [
        (build_loader, _UnknownComponentConfig(type="missing_loader"), "docprep.loaders"),
        (build_parser, _UnknownComponentConfig(type="missing_parser"), "docprep.parsers"),
        (build_chunker, _UnknownComponentConfig(type="missing_chunker"), "docprep.chunkers"),
        (build_sink, _UnknownComponentConfig(type="missing_sink"), "docprep.sinks"),
    ],
)
def test_builders_raise_clear_error_when_component_is_missing(
    builder: Callable[[object], object], config: _UnknownComponentConfig, group: str
) -> None:
    with patch("docprep.registry.discover_entry_points", return_value={}):
        with pytest.raises(
            LookupError, match=f"Unknown plugin '{config.type}' for group '{group}'"
        ):
            builder(cast(object, config))
