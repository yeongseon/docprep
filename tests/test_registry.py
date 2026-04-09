from __future__ import annotations

from pathlib import Path
from typing import cast
import uuid

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker
from docprep.config import (
    HeadingChunkerConfig,
    MarkdownLoaderConfig,
    MarkdownParserConfig,
    SizeChunkerConfig,
    SQLAlchemySinkConfig,
)
from docprep.loaders.markdown import MarkdownLoader
from docprep.models.domain import Document, Section
from docprep.parsers.markdown import MarkdownParser
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
    assert BUILTIN_LOADERS == {"markdown": MarkdownLoader}
    assert BUILTIN_PARSERS == {"markdown": MarkdownParser}
    assert BUILTIN_CHUNKERS == {"heading": HeadingChunker, "size": SizeChunker}
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


def test_build_sink_returns_sqlalchemy_sink_with_created_engine() -> None:
    sink = cast(
        SQLAlchemySink,
        build_sink(SQLAlchemySinkConfig(database_url="sqlite://", create_tables=True)),
    )
    stats = sink.stats()

    assert isinstance(sink, SQLAlchemySink)
    assert (stats.documents, stats.sections, stats.chunks) == (0, 0, 0)
