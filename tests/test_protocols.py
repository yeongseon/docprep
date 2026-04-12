from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import uuid

from sqlalchemy import create_engine

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.protocol import Chunker
from docprep.loaders.filesystem import FileSystemLoader
from docprep.loaders.markdown import MarkdownLoader
from docprep.loaders.protocol import Loader
from docprep.loaders.types import LoadedSource
from docprep.models.domain import Document, SinkUpsertResult
from docprep.parsers.markdown import MarkdownParser
from docprep.parsers.multi import MultiFormatParser
from docprep.parsers.protocol import Parser
from docprep.sinks.protocol import Sink
from docprep.sinks.sqlalchemy import SQLAlchemySink


def test_protocols_are_runtime_checkable() -> None:
    assert isinstance(MarkdownLoader(), Loader)
    assert isinstance(FileSystemLoader(), Loader)
    assert isinstance(MarkdownParser(), Parser)
    assert isinstance(MultiFormatParser(), Parser)
    assert isinstance(HeadingChunker(), Chunker)
    assert isinstance(SQLAlchemySink(engine=create_engine("sqlite://")), Sink)


def test_isinstance_checks_work_for_custom_implementations() -> None:
    class CustomLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return []

    class CustomParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            del loaded_source
            return Document(
                id=uuid.uuid4(),
                source_uri="docs/example.md",
                title="Example",
                source_checksum="checksum",
            )

    class CustomChunker:
        def chunk(self, document: Document) -> Document:
            return document

    class CustomSink:
        def upsert(
            self,
            documents: Sequence[Document],
            *,
            run_id: uuid.UUID | None = None,
        ) -> SinkUpsertResult:
            del documents
            del run_id
            return SinkUpsertResult()

    assert isinstance(CustomLoader(), Loader)
    assert isinstance(CustomParser(), Parser)
    assert isinstance(CustomChunker(), Chunker)
    assert isinstance(CustomSink(), Sink)
