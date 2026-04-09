"""Built-in component registry for config-driven pipeline construction."""

from __future__ import annotations

from collections.abc import Sequence

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.protocol import Chunker
from docprep.chunkers.size import SizeChunker
from docprep.config import (
    ChunkerConfig,
    HeadingChunkerConfig,
    MarkdownLoaderConfig,
    MarkdownParserConfig,
    SQLAlchemySinkConfig,
)
from docprep.loaders.markdown import MarkdownLoader
from docprep.loaders.protocol import Loader
from docprep.parsers.markdown import MarkdownParser
from docprep.parsers.protocol import Parser
from docprep.sinks.protocol import Sink

BUILTIN_LOADERS: dict[str, type[MarkdownLoader]] = {
    "markdown": MarkdownLoader,
}

BUILTIN_PARSERS: dict[str, type[MarkdownParser]] = {
    "markdown": MarkdownParser,
}

BUILTIN_CHUNKERS: dict[str, type[HeadingChunker] | type[SizeChunker]] = {
    "heading": HeadingChunker,
    "size": SizeChunker,
}

BUILTIN_SINKS: dict[str, str] = {
    "sqlalchemy": "docprep.sinks.sqlalchemy.SQLAlchemySink",
}


def build_loader(config: MarkdownLoaderConfig) -> Loader:
    return MarkdownLoader(glob_pattern=config.glob_pattern)


def build_parser(config: MarkdownParserConfig) -> Parser:
    return MarkdownParser()


def build_chunker(config: ChunkerConfig) -> Chunker:
    if isinstance(config, HeadingChunkerConfig):
        return HeadingChunker()
    return SizeChunker(max_chars=config.max_chars)


def build_chunkers(configs: Sequence[ChunkerConfig]) -> tuple[Chunker, ...]:
    return tuple(build_chunker(c) for c in configs)


def build_sink(config: SQLAlchemySinkConfig) -> Sink:
    from sqlalchemy import create_engine

    from docprep.sinks.sqlalchemy import SQLAlchemySink

    engine = create_engine(config.database_url)
    return SQLAlchemySink(engine=engine, create_tables=config.create_tables)
