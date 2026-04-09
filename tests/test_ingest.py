from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker
from docprep.exceptions import IngestError
from docprep.ingest import Ingestor, ingest
from docprep.loaders.protocol import Loader
from docprep.loaders.types import LoadedSource
from docprep.models.domain import Document
from docprep.parsers.protocol import Parser
from docprep.sinks.orm import DocumentRow
from docprep.sinks.sqlalchemy import SQLAlchemySink


class FailingLoader:
    def load(self, source: str | Path) -> list[LoadedSource]:
        raise RuntimeError(f"bad load: {source}")


class FailingParser:
    def parse(self, loaded_source: LoadedSource) -> Document:
        raise RuntimeError(f"bad parse: {loaded_source.source_uri}")


def test_ingestor_with_defaults_processes_markdown_file(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    result = Ingestor().run(path)

    assert len(result.documents) == 1
    assert result.documents[0].title == "Title"
    assert len(result.documents[0].sections) == 1
    assert result.documents[0].chunks == ()


def test_ingestor_with_sink_persists_documents(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)

    result = Ingestor(chunkers=[HeadingChunker(), SizeChunker()], sink=sink).run(path)

    assert result.persisted is True
    assert result.sink_name == "SQLAlchemySink"
    with Session(engine) as session:
        assert session.execute(select(DocumentRow)).scalar_one().title == "Title"


def test_ingestor_with_custom_chunkers_works(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nSentence one. Sentence two.\n", encoding="utf-8")

    result = Ingestor(chunkers=[HeadingChunker(), SizeChunker(max_chars=15)]).run(path)

    assert len(result.documents[0].sections) == 1
    assert len(result.documents[0].chunks) == 2


def test_ingest_convenience_function_works(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    result = ingest(path, chunkers=[HeadingChunker()])

    assert len(result.documents) == 1
    assert result.documents[0].source_uri == path.as_posix()


def test_ingest_error_is_raised_for_load_failure(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="Loading failed"):
        _ = Ingestor(loader=FailingLoader()).run(tmp_path)


def test_ingest_error_is_raised_for_parse_failure(tmp_path: Path) -> None:
    loaded_source = LoadedSource(
        source_path="docs/example.md",
        source_uri="docs/example.md",
        raw_text="Body",
        checksum="checksum",
    )

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    assert isinstance(SingleLoader(), Loader)
    assert isinstance(FailingParser(), Parser)
    with pytest.raises(IngestError, match="Processing failed"):
        _ = Ingestor(loader=SingleLoader(), parser=FailingParser()).run(tmp_path)
