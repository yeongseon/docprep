"""Ingestor — orchestrates the document ingestion pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.protocol import Chunker
from docprep.exceptions import IngestError
from docprep.loaders.markdown import MarkdownLoader
from docprep.loaders.protocol import Loader
from docprep.models.domain import Document, IngestResult
from docprep.parsers.markdown import MarkdownParser
from docprep.parsers.protocol import Parser
from docprep.sinks.protocol import Sink


class Ingestor:
    """Orchestrates the load → parse → chunk → (optional sink) pipeline."""

    def __init__(
        self,
        *,
        loader: Loader | None = None,
        parser: Parser | None = None,
        chunkers: Sequence[Chunker] | None = None,
        sink: Sink | None = None,
    ) -> None:
        self._loader = loader or MarkdownLoader()
        self._parser = parser or MarkdownParser()
        self._chunkers: Sequence[Chunker] = chunkers if chunkers is not None else [HeadingChunker()]
        self._sink = sink

    def run(self, source: str | Path) -> IngestResult:
        try:
            loaded_sources = list(self._loader.load(source))
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


def ingest(
    source: str | Path,
    *,
    loader: Loader | None = None,
    parser: Parser | None = None,
    chunkers: Sequence[Chunker] | None = None,
    sink: Sink | None = None,
) -> IngestResult:
    """Convenience function for a single ingest run."""
    return Ingestor(
        loader=loader,
        parser=parser,
        chunkers=chunkers,
        sink=sink,
    ).run(source)
