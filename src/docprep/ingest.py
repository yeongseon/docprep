"""Ingestor — orchestrates the document ingestion pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.protocol import Chunker
from docprep.config import DocPrepConfig
from docprep.exceptions import ConfigError, IngestError
from docprep.loaders.protocol import Loader
from docprep.models.domain import Document, IngestResult
from docprep.parsers.protocol import Parser
from docprep.sinks.protocol import Sink


class Ingestor:
    """Orchestrates the load → parse → chunk → (optional sink) pipeline."""

    def __init__(
        self,
        *,
        config: DocPrepConfig | None = None,
        loader: Loader | None = None,
        parser: Parser | None = None,
        chunkers: Sequence[Chunker] | None = None,
        sink: Sink | None = None,
    ) -> None:
        self._config = config
        self._loader = loader if loader is not None else self._loader_from_config(config)
        self._parser = parser if parser is not None else self._parser_from_config(config)
        self._chunkers: Sequence[Chunker] = (
            chunkers if chunkers is not None else self._chunkers_from_config(config)
        )
        self._sink = sink if sink is not None else self._sink_from_config(config)

    def run(self, source: str | Path | None = None) -> IngestResult:
        resolved_source = self._resolve_source(source)
        try:
            loaded_sources = list(self._loader.load(resolved_source))
        except Exception as exc:
            raise IngestError(f"Loading failed: {exc}") from exc

        documents: list[Document] = []
        for ls in loaded_sources:
            try:
                doc = self._parser.parse(ls)
                for chunker in self._chunkers:
                    doc = chunker.chunk(doc)
                documents.append(doc)
            except Exception as exc:
                raise IngestError(f"Processing failed for {ls.source_uri}: {exc}") from exc

        skipped: tuple[str, ...] = ()
        persisted = False
        sink_name: str | None = None

        if self._sink is not None:
            try:
                skipped = self._sink.upsert(documents)
                persisted = True
                sink_name = type(self._sink).__name__
            except Exception as exc:
                raise IngestError(f"Sink failed: {exc}") from exc

        return IngestResult(
            documents=tuple(documents),
            skipped_source_uris=skipped,
            persisted=persisted,
            sink_name=sink_name,
        )

    def _resolve_source(self, source: str | Path | None) -> str | Path:
        """Resolve source: explicit arg > config.resolved_source() > error."""
        if source is not None:
            return source
        if self._config is not None:
            resolved = self._config.resolved_source()
            if resolved is not None:
                return resolved
        raise ConfigError("No source specified: pass source argument or set 'source' in config")

    @staticmethod
    def _loader_from_config(config: DocPrepConfig | None) -> Loader:
        if config is not None and config.loader is not None:
            from docprep.registry import build_loader

            return build_loader(config.loader)
        from docprep.loaders.markdown import MarkdownLoader

        return MarkdownLoader()

    @staticmethod
    def _parser_from_config(config: DocPrepConfig | None) -> Parser:
        if config is not None and config.parser is not None:
            from docprep.registry import build_parser

            return build_parser(config.parser)
        from docprep.parsers.markdown import MarkdownParser

        return MarkdownParser()

    @staticmethod
    def _chunkers_from_config(config: DocPrepConfig | None) -> Sequence[Chunker]:
        if config is not None and config.chunkers is not None:
            from docprep.registry import build_chunkers

            return build_chunkers(config.chunkers)
        return [HeadingChunker()]

    @staticmethod
    def _sink_from_config(config: DocPrepConfig | None) -> Sink | None:
        if config is not None and config.sink is not None:
            from docprep.registry import build_sink

            return build_sink(config.sink)
        return None


def ingest(
    source: str | Path | None = None,
    *,
    config: DocPrepConfig | None = None,
    loader: Loader | None = None,
    parser: Parser | None = None,
    chunkers: Sequence[Chunker] | None = None,
    sink: Sink | None = None,
) -> IngestResult:
    """Convenience function for a single ingest run."""
    return Ingestor(
        config=config,
        loader=loader,
        parser=parser,
        chunkers=chunkers,
        sink=sink,
    ).run(source)
