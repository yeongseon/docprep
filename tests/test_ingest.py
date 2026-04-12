from __future__ import annotations

from collections.abc import Sequence
import importlib
import logging
from pathlib import Path
import time
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from typing_extensions import override

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker
from docprep.config import (
    DocPrepConfig,
    HeadingChunkerConfig,
    MarkdownLoaderConfig,
    MarkdownParserConfig,
    SizeChunkerConfig,
    SQLAlchemySinkConfig,
)
from docprep.exceptions import ConfigError, IngestError
from docprep.ingest import Ingestor, ingest
from docprep.loaders.protocol import Loader
from docprep.loaders.types import LoadedSource
from docprep.models.domain import (
    Document,
    DocumentError,
    ErrorMode,
    IngestStageReport,
    PipelineStage,
    RunManifest,
    SinkUpsertResult,
    SourceScope,
)
from docprep.parsers.protocol import Parser
from docprep.progress import IngestProgressEvent
from docprep.sinks.orm import DocumentRow
from docprep.sinks.sqlalchemy import SQLAlchemySink


class FailingLoader:
    def load(self, source: str | Path) -> list[LoadedSource]:
        raise RuntimeError(f"bad load: {source}")


class FailingParser:
    def parse(self, loaded_source: LoadedSource) -> Document:
        raise RuntimeError(f"bad parse: {loaded_source.source_uri}")


class FailingChunker:
    def chunk(self, document: Document) -> Document:
        raise RuntimeError(f"bad chunk: {document.source_uri}")


class CapturingHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class RecordingSink:
    def __init__(self, *, result: SinkUpsertResult | None = None) -> None:
        self.result: SinkUpsertResult = result or SinkUpsertResult()
        self.documents: tuple[Document, ...] = ()
        self.run_ids: tuple[uuid.UUID | None, ...] = ()
        self.manifests: tuple[RunManifest, ...] = ()

    def upsert(
        self,
        documents: Sequence[Document],
        *,
        run_id: uuid.UUID | None = None,
    ) -> SinkUpsertResult:
        self.documents = self.documents + tuple(documents)
        self.run_ids = self.run_ids + (run_id,)
        return self.result

    def record_run(self, manifest: RunManifest) -> None:
        self.manifests = self.manifests + (manifest,)


class SelectivelyFailingSink:
    def __init__(self, *, fail_uris: set[str]) -> None:
        self.fail_uris = fail_uris
        self.upserted: list[str] = []

    def upsert(
        self,
        documents: Sequence[Document],
        *,
        run_id: uuid.UUID | None = None,
    ) -> SinkUpsertResult:
        del run_id
        for doc in documents:
            if doc.source_uri in self.fail_uris:
                raise RuntimeError(f"sink fail: {doc.source_uri}")
        self.upserted.extend(doc.source_uri for doc in documents)
        return SinkUpsertResult(
            updated_source_uris=tuple(doc.source_uri for doc in documents),
        )


def _loaded_source(*, source_uri: str, raw_text: str = "# Title\n\nBody\n") -> LoadedSource:
    return LoadedSource(
        source_path=source_uri,
        source_uri=source_uri,
        raw_text=raw_text,
        checksum=f"checksum-{source_uri}",
    )


def _document_from_loaded_source(loaded_source: LoadedSource) -> Document:
    return Document(
        id=uuid.uuid4(),
        source_uri=loaded_source.source_uri,
        title=Path(loaded_source.source_uri).stem,
        source_checksum=loaded_source.checksum,
    )


def test_ingestor_with_defaults_processes_markdown_file(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    result = Ingestor().run(path)

    assert len(result.documents) == 1
    assert result.documents[0].title == "Title"
    assert len(result.documents[0].sections) == 1
    assert len(result.documents[0].chunks) == 1  # SizeChunker now in defaults
    assert result.processed_count == 1
    assert result.failed_count == 0
    assert result.run_manifest is not None
    assert result.run_manifest.scope == SourceScope(prefixes=("file:guide.md",), explicit=False)
    assert result.run_manifest.source_uris_seen == ("file:guide.md",)


def test_ingestor_default_parser_dispatches_by_media_type() -> None:
    plain = LoadedSource(
        source_path="notes.txt",
        source_uri="file:notes.txt",
        raw_text="Plain title\nBody",
        checksum="checksum",
        media_type="text/plain",
    )
    html = LoadedSource(
        source_path="page.html",
        source_uri="file:page.html",
        raw_text="<h1>Html Title</h1><p>Body</p>",
        checksum="checksum2",
        media_type="text/html",
    )

    class MultiSourceLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [plain, html]

    result = Ingestor(loader=MultiSourceLoader()).run("ignored")

    assert [doc.source_type for doc in result.documents] == ["plaintext", "html"]
    assert [doc.title for doc in result.documents] == ["Plain title", "Html Title"]


def test_default_chunkers_are_heading_and_size() -> None:
    """DEFAULT_CHUNKERS is the single source of truth for the default pipeline."""
    from docprep.ingest import DEFAULT_CHUNKERS

    assert len(DEFAULT_CHUNKERS) == 2
    assert isinstance(DEFAULT_CHUNKERS[0], HeadingChunker)
    assert isinstance(DEFAULT_CHUNKERS[1], SizeChunker)


def test_ingestor_default_matches_cli_default(tmp_path: Path) -> None:
    """CLI and API must produce identical output for the same input when no config is given."""
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nParagraph one. Paragraph two.\n", encoding="utf-8")

    # API path
    api_result = Ingestor().run(path)

    # CLI path (simulates what _cmd_ingest / _cmd_preview do)
    from docprep.ingest import DEFAULT_CHUNKERS

    cli_result = Ingestor(chunkers=list(DEFAULT_CHUNKERS)).run(path)

    assert len(api_result.documents) == len(cli_result.documents)
    for api_doc, cli_doc in zip(api_result.documents, cli_result.documents):
        assert len(api_doc.sections) == len(cli_doc.sections)
        assert len(api_doc.chunks) == len(cli_doc.chunks)
        assert [c.content_text for c in api_doc.chunks] == [c.content_text for c in cli_doc.chunks]


def test_ingestor_with_sink_persists_documents(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")
    engine = create_engine("sqlite://")
    sink = SQLAlchemySink(engine=engine)

    result = Ingestor(chunkers=[HeadingChunker(), SizeChunker()], sink=sink).run(path)

    assert result.persisted is True
    assert result.sink_name == "SQLAlchemySink"
    assert result.updated_count == 1
    assert result.updated_source_uris == ("file:guide.md",)
    assert result.skipped_source_uris == ()
    assert result.run_manifest is not None
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
    assert result.documents[0].source_uri == "file:guide.md"
    assert result.processed_count == 1


def test_ingest_convenience_function_accepts_workers(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")

    result = ingest(path, workers=2)

    assert len(result.documents) == 1
    assert result.processed_count == 1


def test_ingestor_workers_parallel_produces_same_result(tmp_path: Path) -> None:
    for idx in range(5):
        _ = (tmp_path / f"doc{idx}.md").write_text(
            f"# Doc {idx}\n\nBody {idx}\n",
            encoding="utf-8",
        )

    result_seq = Ingestor().run(tmp_path, workers=1)
    result_par = Ingestor().run(tmp_path, workers=2)

    assert len(result_seq.documents) == len(result_par.documents)
    assert [doc.source_uri for doc in result_seq.documents] == [
        doc.source_uri for doc in result_par.documents
    ]
    assert [doc.id for doc in result_seq.documents] == [doc.id for doc in result_par.documents]
    assert result_seq.processed_count == result_par.processed_count


def test_ingestor_resume_skips_unchanged(tmp_path: Path) -> None:
    first_source = _loaded_source(source_uri="docs/a.md")
    second_source = _loaded_source(source_uri="docs/b.md")
    parsed: list[str] = []
    checkpoint_path = tmp_path / "checkpoint.json"

    class MultiLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [first_source, second_source]

    class TrackingParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            parsed.append(loaded_source.source_uri)
            return _document_from_loaded_source(loaded_source)

    ingestor = Ingestor(loader=MultiLoader(), parser=TrackingParser(), chunkers=[])
    first = ingestor.run("ignored", resume=True, checkpoint_path=checkpoint_path)

    assert first.processed_count == 2
    assert first.skipped_count == 0
    assert parsed == [first_source.source_uri, second_source.source_uri]

    parsed.clear()
    second = ingestor.run("ignored", resume=True, checkpoint_path=checkpoint_path)

    assert second.processed_count == 0
    assert second.skipped_count == 2
    assert second.skipped_source_uris == (first_source.source_uri, second_source.source_uri)
    assert parsed == []


def test_ingestor_resume_reprocesses_changed(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "checkpoint.json"
    parsed: list[str] = []
    source = _loaded_source(source_uri="docs/a.md")

    class MutableLoader:
        def __init__(self) -> None:
            self.sources: list[LoadedSource] = [source]

        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return list(self.sources)

    class TrackingParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            parsed.append(loaded_source.checksum)
            return _document_from_loaded_source(loaded_source)

    loader = MutableLoader()
    ingestor = Ingestor(loader=loader, parser=TrackingParser(), chunkers=[])
    _ = ingestor.run("ignored", resume=True, checkpoint_path=checkpoint_path)

    loader.sources = [
        LoadedSource(
            source_path=source.source_path,
            source_uri=source.source_uri,
            raw_text=source.raw_text + "changed",
            checksum="checksum-updated",
            media_type=source.media_type,
        )
    ]

    second = ingestor.run("ignored", resume=True, checkpoint_path=checkpoint_path)

    assert second.processed_count == 1
    assert second.skipped_count == 0
    assert parsed == [source.checksum, "checksum-updated"]


def test_ingestor_resume_config_invalidation(tmp_path: Path) -> None:
    loaded_source = _loaded_source(source_uri="docs/a.md")
    checkpoint_path = tmp_path / "checkpoint.json"
    parsed: list[str] = []

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class TrackingParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            parsed.append(loaded_source.source_uri)
            return _document_from_loaded_source(loaded_source)

    config_a = DocPrepConfig(
        chunkers=(SizeChunkerConfig(max_chars=128),),
        config_path=tmp_path / "docprep-a.toml",
    )
    _ = Ingestor(
        config=config_a,
        loader=SingleLoader(),
        parser=TrackingParser(),
        chunkers=[],
    ).run("ignored", resume=True, checkpoint_path=checkpoint_path)

    config_b = DocPrepConfig(
        chunkers=(SizeChunkerConfig(max_chars=256),),
        config_path=tmp_path / "docprep-b.toml",
    )
    second = Ingestor(
        config=config_b,
        loader=SingleLoader(),
        parser=TrackingParser(),
        chunkers=[],
    ).run("ignored", resume=True, checkpoint_path=checkpoint_path)

    assert second.processed_count == 1
    assert second.skipped_count == 0
    assert parsed == [loaded_source.source_uri, loaded_source.source_uri]


def test_ingestor_resume_with_workers(tmp_path: Path) -> None:
    first_source = _loaded_source(source_uri="docs/a.md")
    second_source = _loaded_source(source_uri="docs/b.md")
    third_source = _loaded_source(source_uri="docs/c.md")
    parsed: list[str] = []
    checkpoint_path = tmp_path / "checkpoint.json"

    class MultiLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [first_source, second_source, third_source]

    class TrackingParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            parsed.append(loaded_source.source_uri)
            return _document_from_loaded_source(loaded_source)

    ingestor = Ingestor(loader=MultiLoader(), parser=TrackingParser(), chunkers=[])
    first = ingestor.run("ignored", workers=3, resume=True, checkpoint_path=checkpoint_path)

    assert first.processed_count == 3
    parsed.clear()

    second = ingestor.run("ignored", workers=3, resume=True, checkpoint_path=checkpoint_path)

    assert second.processed_count == 0
    assert second.skipped_count == 3
    assert parsed == []


def test_ingestor_resume_no_checkpoint_file(tmp_path: Path) -> None:
    loaded_source = _loaded_source(source_uri="docs/a.md")
    checkpoint_path = tmp_path / "new-checkpoint.json"

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    result = Ingestor(loader=SingleLoader(), parser=PassthroughParser(), chunkers=[]).run(
        "ignored",
        resume=True,
        checkpoint_path=checkpoint_path,
    )

    assert result.processed_count == 1
    assert checkpoint_path.exists()


def test_ingestor_resume_after_interrupted_run(tmp_path: Path) -> None:
    first_source = _loaded_source(source_uri="docs/a.md")
    second_source = _loaded_source(source_uri="docs/b.md")
    checkpoint_path = tmp_path / "checkpoint.json"

    class MultiLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [first_source, second_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    class FailSecondSink:
        def upsert(
            self,
            documents: Sequence[Document],
            *,
            run_id: uuid.UUID | None = None,
        ) -> SinkUpsertResult:
            del run_id
            doc = documents[0]
            if doc.source_uri == second_source.source_uri:
                raise RuntimeError("sink fail")
            return SinkUpsertResult(updated_source_uris=(doc.source_uri,))

    with pytest.raises(IngestError, match="Persist failed for docs/b.md"):
        _ = Ingestor(
            loader=MultiLoader(),
            parser=PassthroughParser(),
            chunkers=[],
            sink=FailSecondSink(),
            error_mode=ErrorMode.FAIL_FAST,
        ).run("ignored", resume=True, checkpoint_path=checkpoint_path)

    second_run = Ingestor(
        loader=MultiLoader(),
        parser=PassthroughParser(),
        chunkers=[],
    ).run("ignored", resume=True, checkpoint_path=checkpoint_path)

    assert second_run.skipped_source_uris == (first_source.source_uri,)
    assert second_run.processed_count == 1
    assert second_run.documents[0].source_uri == second_source.source_uri


def test_ingestor_workers_with_errors_continue(tmp_path: Path) -> None:
    first_source = _loaded_source(source_uri="docs/ok-a.md")
    failing_source = _loaded_source(source_uri="docs/fail.md")
    second_source = _loaded_source(source_uri="docs/ok-b.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [first_source, failing_source, second_source]

    class SelectivelyFailingParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            if loaded_source.source_uri == failing_source.source_uri:
                raise RuntimeError(f"bad parse: {loaded_source.source_uri}")
            return _document_from_loaded_source(loaded_source)

    result = Ingestor(
        loader=SingleLoader(),
        parser=SelectivelyFailingParser(),
        chunkers=[],
        error_mode=ErrorMode.CONTINUE_ON_ERROR,
    ).run(tmp_path, workers=2)

    assert [doc.source_uri for doc in result.documents] == [
        first_source.source_uri,
        second_source.source_uri,
    ]
    assert result.processed_count == 2
    assert result.failed_source_uris == (failing_source.source_uri,)


def test_ingestor_workers_with_errors_fail_fast(tmp_path: Path) -> None:
    first_source = _loaded_source(source_uri="docs/fail.md")
    second_source = _loaded_source(source_uri="docs/ok.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [first_source, second_source]

    class SelectivelyFailingParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            if loaded_source.source_uri == first_source.source_uri:
                raise RuntimeError(f"bad parse: {loaded_source.source_uri}")
            return _document_from_loaded_source(loaded_source)

    with pytest.raises(IngestError, match="parse failed for docs/fail.md"):
        _ = Ingestor(
            loader=SingleLoader(),
            parser=SelectivelyFailingParser(),
            chunkers=[],
            error_mode=ErrorMode.FAIL_FAST,
        ).run(tmp_path, workers=2)


def test_ingestor_workers_one_is_sequential(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded_source = _loaded_source(source_uri="docs/one.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    class FailingExecutor:
        def __init__(self, max_workers: int) -> None:
            del max_workers
            raise AssertionError("ThreadPoolExecutor should not be used")

    ingest_module = importlib.import_module("docprep.ingest")
    monkeypatch.setattr(ingest_module, "ThreadPoolExecutor", FailingExecutor)

    result = Ingestor(loader=SingleLoader(), parser=PassthroughParser(), chunkers=[]).run(
        tmp_path,
        workers=1,
    )

    assert result.processed_count == 1


def test_ingestor_workers_with_sink_persists_in_order(tmp_path: Path) -> None:
    first_source = _loaded_source(source_uri="docs/a.md")
    second_source = _loaded_source(source_uri="docs/b.md")
    third_source = _loaded_source(source_uri="docs/c.md")
    delays = {
        first_source.source_uri: 0.03,
        second_source.source_uri: 0.01,
        third_source.source_uri: 0.0,
    }
    sink = RecordingSink()

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [first_source, second_source, third_source]

    class DelayedParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            time.sleep(delays[loaded_source.source_uri])
            return _document_from_loaded_source(loaded_source)

    _ = Ingestor(
        loader=SingleLoader(),
        parser=DelayedParser(),
        chunkers=[],
        sink=sink,
    ).run(tmp_path, workers=3)

    assert [doc.source_uri for doc in sink.documents] == [
        first_source.source_uri,
        second_source.source_uri,
        third_source.source_uri,
    ]


def test_ingest_error_is_raised_for_load_failure(tmp_path: Path) -> None:
    with pytest.raises(IngestError, match="Loading failed"):
        _ = Ingestor(loader=FailingLoader()).run(tmp_path)


def test_ingestor_continues_after_parse_failure(tmp_path: Path) -> None:
    loaded_source = _loaded_source(source_uri="docs/example.md", raw_text="Body")
    other_source = _loaded_source(source_uri="docs/other.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source, other_source]

    class SometimesFailingParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            if loaded_source.source_uri == "docs/example.md":
                raise RuntimeError(f"bad parse: {loaded_source.source_uri}")
            return _document_from_loaded_source(loaded_source)

    assert isinstance(SingleLoader(), Loader)
    assert isinstance(SometimesFailingParser(), Parser)

    ingestor = Ingestor(
        loader=SingleLoader(),
        parser=SometimesFailingParser(),
        chunkers=[],
    )
    result = ingestor.run(tmp_path)

    assert len(result.documents) == 1
    assert result.documents[0].source_uri == "docs/other.md"
    assert result.processed_count == 1
    assert result.failed_count == 1
    assert result.failed_source_uris == ("docs/example.md",)


def test_ingestor_continues_after_chunk_failure(tmp_path: Path) -> None:
    first_source = _loaded_source(source_uri="docs/example.md")
    second_source = _loaded_source(source_uri="docs/other.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [first_source, second_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    class SometimesFailingChunker:
        def chunk(self, document: Document) -> Document:
            if document.source_uri == "docs/example.md":
                raise RuntimeError(f"bad chunk: {document.source_uri}")
            return document

    result = Ingestor(
        loader=SingleLoader(),
        parser=PassthroughParser(),
        chunkers=[SometimesFailingChunker()],
    ).run(tmp_path)

    assert len(result.documents) == 1
    assert result.documents[0].source_uri == "docs/other.md"
    assert result.processed_count == 1
    assert result.failed_count == 1
    assert result.failed_source_uris == ("docs/example.md",)


def test_ingestor_fail_fast_stops_on_first_parse_error(tmp_path: Path) -> None:
    failing_source = _loaded_source(source_uri="docs/failing.md")
    next_source = _loaded_source(source_uri="docs/next.md")
    parse_attempts: list[str] = []

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [failing_source, next_source]

    class SometimesFailingParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            parse_attempts.append(loaded_source.source_uri)
            if loaded_source.source_uri == failing_source.source_uri:
                raise RuntimeError(f"bad parse: {loaded_source.source_uri}")
            return _document_from_loaded_source(loaded_source)

    with pytest.raises(IngestError, match="parse failed for docs/failing.md"):
        _ = Ingestor(
            loader=SingleLoader(),
            parser=SometimesFailingParser(),
            chunkers=[],
            error_mode=ErrorMode.FAIL_FAST,
        ).run(tmp_path)

    assert parse_attempts == ["docs/failing.md"]


def test_ingestor_fail_fast_stops_on_first_chunk_error(tmp_path: Path) -> None:
    failing_source = _loaded_source(source_uri="docs/failing.md")
    next_source = _loaded_source(source_uri="docs/next.md")
    chunk_attempts: list[str] = []

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [failing_source, next_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    class SometimesFailingChunker:
        def chunk(self, document: Document) -> Document:
            chunk_attempts.append(document.source_uri)
            if document.source_uri == failing_source.source_uri:
                raise RuntimeError(f"bad chunk: {document.source_uri}")
            return document

    with pytest.raises(IngestError, match="chunk failed for docs/failing.md"):
        _ = Ingestor(
            loader=SingleLoader(),
            parser=PassthroughParser(),
            chunkers=[SometimesFailingChunker()],
            error_mode=ErrorMode.FAIL_FAST,
        ).run(tmp_path)

    assert chunk_attempts == ["docs/failing.md"]


def test_ingestor_continue_on_error_collects_structured_errors(tmp_path: Path) -> None:
    failing_source = _loaded_source(source_uri="docs/failing.md")
    next_source = _loaded_source(source_uri="docs/next.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [failing_source, next_source]

    class SometimesFailingParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            if loaded_source.source_uri == failing_source.source_uri:
                raise RuntimeError(f"bad parse: {loaded_source.source_uri}")
            return _document_from_loaded_source(loaded_source)

    result = Ingestor(
        loader=SingleLoader(),
        parser=SometimesFailingParser(),
        chunkers=[],
        error_mode=ErrorMode.CONTINUE_ON_ERROR,
    ).run(tmp_path)

    assert len(result.errors) == 1
    assert result.errors[0] == DocumentError(
        source_uri="docs/failing.md",
        stage=PipelineStage.PARSE,
        error_type="RuntimeError",
        message="bad parse: docs/failing.md",
    )


def test_ingestor_persist_failure_per_document_does_not_affect_others(tmp_path: Path) -> None:
    first_source = _loaded_source(source_uri="docs/failing.md")
    second_source = _loaded_source(source_uri="docs/ok.md")
    sink = SelectivelyFailingSink(fail_uris={"docs/failing.md"})

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [first_source, second_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    result = Ingestor(
        loader=SingleLoader(),
        parser=PassthroughParser(),
        chunkers=[],
        sink=sink,
        error_mode=ErrorMode.CONTINUE_ON_ERROR,
    ).run(tmp_path)

    assert sink.upserted == ["docs/ok.md"]
    assert result.updated_source_uris == ("docs/ok.md",)
    assert result.failed_count == 1
    assert result.errors[0] == DocumentError(
        source_uri="docs/failing.md",
        stage=PipelineStage.PERSIST,
        error_type="RuntimeError",
        message="sink fail: docs/failing.md",
    )


def test_ingestor_fail_fast_stops_on_persist_failure(tmp_path: Path) -> None:
    first_source = _loaded_source(source_uri="docs/failing.md")
    second_source = _loaded_source(source_uri="docs/ok.md")
    sink = SelectivelyFailingSink(fail_uris={"docs/failing.md"})

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [first_source, second_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    with pytest.raises(IngestError, match="Persist failed for docs/failing.md"):
        _ = Ingestor(
            loader=SingleLoader(),
            parser=PassthroughParser(),
            chunkers=[],
            sink=sink,
            error_mode=ErrorMode.FAIL_FAST,
        ).run(tmp_path)

    assert sink.upserted == []


def test_document_error_in_ingest_result(tmp_path: Path) -> None:
    failing_source = _loaded_source(source_uri="docs/failing.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [failing_source]

    result = Ingestor(
        loader=SingleLoader(),
        parser=FailingParser(),
        chunkers=[],
        error_mode=ErrorMode.CONTINUE_ON_ERROR,
    ).run(tmp_path)

    assert result.errors == (
        DocumentError(
            source_uri="docs/failing.md",
            stage=PipelineStage.PARSE,
            error_type="RuntimeError",
            message="bad parse: docs/failing.md",
        ),
    )
    assert result.failed_source_uris == ("docs/failing.md",)


def test_ingestor_per_document_atomicity_with_sqlalchemy(tmp_path: Path) -> None:
    first_source = _loaded_source(source_uri="docs/ok.md")
    second_source = _loaded_source(source_uri="docs/failing.md")
    engine = create_engine("sqlite://")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [first_source, second_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    class FailingOnUriSQLAlchemySink:
        def __init__(self, *, fail_uris: set[str]) -> None:
            self._delegate = SQLAlchemySink(engine=engine)
            self._fail_uris = fail_uris

        def upsert(
            self,
            documents: Sequence[Document],
            *,
            run_id: uuid.UUID | None = None,
        ) -> SinkUpsertResult:
            for doc in documents:
                if doc.source_uri in self._fail_uris:
                    raise RuntimeError(f"sink fail: {doc.source_uri}")
            return self._delegate.upsert(documents, run_id=run_id)

        def record_run(self, manifest: RunManifest) -> None:
            self._delegate.record_run(manifest)

    result = Ingestor(
        loader=SingleLoader(),
        parser=PassthroughParser(),
        chunkers=[],
        sink=FailingOnUriSQLAlchemySink(fail_uris={"docs/failing.md"}),
        error_mode=ErrorMode.CONTINUE_ON_ERROR,
    ).run(tmp_path)

    with Session(engine) as session:
        ok_row = session.execute(
            select(DocumentRow).where(DocumentRow.source_uri == "docs/ok.md")
        ).scalar_one_or_none()
        failing_row = session.execute(
            select(DocumentRow).where(DocumentRow.source_uri == "docs/failing.md")
        ).scalar_one_or_none()

    assert ok_row is not None
    assert failing_row is None
    assert result.failed_source_uris == ("docs/failing.md",)


def test_ingestor_with_config_builds_and_runs_pipeline(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    path = docs_dir / "guide.md"
    _ = path.write_text("# Title\n\nSentence one. Sentence two.\n", encoding="utf-8")
    db_path = tmp_path / "docs.db"
    config = DocPrepConfig(
        source="docs",
        loader=MarkdownLoaderConfig(),
        parser=MarkdownParserConfig(),
        chunkers=(HeadingChunkerConfig(), SizeChunkerConfig(max_chars=15)),
        sink=SQLAlchemySinkConfig(database_url=f"sqlite:///{db_path}"),
        config_path=tmp_path / "docprep.toml",
    )

    result = Ingestor(config=config).run()

    assert result.persisted is True
    assert result.sink_name == "SQLAlchemySink"
    assert len(result.documents) == 1
    assert len(result.documents[0].sections) == 1
    assert len(result.documents[0].chunks) == 2
    assert result.processed_count == 1
    assert result.updated_count == 1


def test_ingestor_config_passes_overlap_and_min_chars_to_size_chunker(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    path = docs_dir / "guide.md"
    _ = path.write_text("# Title\n\nabcdefghij", encoding="utf-8")
    config = DocPrepConfig(
        source="docs",
        chunkers=(
            HeadingChunkerConfig(),
            SizeChunkerConfig(max_chars=4, overlap_chars=2, min_chars=2),
        ),
        config_path=tmp_path / "docprep.toml",
    )

    result = Ingestor(config=config).run()

    assert [chunk.content_text for chunk in result.documents[0].chunks] == [
        "abcd",
        "cdefgh",
        "ghij",
    ]


def test_ingestor_uses_config_source_when_run_source_is_none(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    path = docs_dir / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")
    config = DocPrepConfig(source="docs", config_path=tmp_path / "docprep.toml")

    result = Ingestor(config=config).run()

    assert result.documents[0].source_uri == "file:guide.md"


def test_ingestor_raises_config_error_when_no_source_available() -> None:
    with pytest.raises(ConfigError, match="No source specified"):
        _ = Ingestor(config=DocPrepConfig()).run()


def test_ingestor_explicit_source_overrides_config_source(tmp_path: Path) -> None:
    config_docs = tmp_path / "config-docs"
    config_docs.mkdir()
    explicit_docs = tmp_path / "explicit-docs"
    explicit_docs.mkdir()
    _ = (config_docs / "config.md").write_text("# Config Title\n\nBody\n", encoding="utf-8")
    explicit_path = explicit_docs / "explicit.md"
    _ = explicit_path.write_text("# Explicit Title\n\nBody\n", encoding="utf-8")
    config = DocPrepConfig(source="config-docs", config_path=tmp_path / "docprep.toml")

    result = Ingestor(config=config).run(explicit_path)

    assert result.documents[0].title == "Explicit Title"
    assert result.documents[0].source_uri == "file:explicit.md"


def test_ingest_convenience_function_supports_config(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    path = docs_dir / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")
    config = DocPrepConfig(source="docs", config_path=tmp_path / "docprep.toml")

    result = ingest(config=config)

    assert len(result.documents) == 1
    assert result.documents[0].source_uri == "file:guide.md"


def test_ingestor_with_configured_sqlalchemy_sink_persists_documents(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    _ = (docs_dir / "guide.md").write_text("# Title\n\nBody\n", encoding="utf-8")
    engine = create_engine("sqlite://")
    config = DocPrepConfig(
        source="docs",
        chunkers=(HeadingChunkerConfig(), SizeChunkerConfig()),
        sink=SQLAlchemySinkConfig(database_url="sqlite://"),
        config_path=tmp_path / "docprep.toml",
    )

    result = Ingestor(
        config=config,
        sink=SQLAlchemySink(engine=engine),
    ).run()

    assert result.persisted is True
    assert result.updated_count == 1
    with Session(engine) as session:
        assert session.execute(select(DocumentRow)).scalar_one().title == "Title"


def test_explicit_loader_overrides_config_loader(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")
    config = DocPrepConfig(
        loader=MarkdownLoaderConfig(glob_pattern="**/*.txt"),
        config_path=tmp_path / "docprep.toml",
    )
    from docprep.loaders.markdown import MarkdownLoader

    result = Ingestor(config=config, loader=MarkdownLoader()).run(path)

    assert len(result.documents) == 1


def test_explicit_parser_overrides_config_parser(tmp_path: Path) -> None:
    path = tmp_path / "guide.md"
    _ = path.write_text("# Title\n\nBody\n", encoding="utf-8")
    config = DocPrepConfig(
        parser=MarkdownParserConfig(),
        config_path=tmp_path / "docprep.toml",
    )
    from docprep.parsers.markdown import MarkdownParser

    result = Ingestor(config=config, parser=MarkdownParser()).run(path)

    assert len(result.documents) == 1


def test_ingestor_emits_progress_events() -> None:
    loaded_source = _loaded_source(source_uri="docs/example.md")
    events: list[IngestProgressEvent] = []

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    sink = RecordingSink(
        result=SinkUpsertResult(
            skipped_source_uris=(loaded_source.source_uri,),
            updated_source_uris=(loaded_source.source_uri,),
        )
    )

    result = Ingestor(
        loader=SingleLoader(),
        parser=PassthroughParser(),
        chunkers=[],
        sink=sink,
        progress_callback=events.append,
    ).run("ignored")

    assert result.processed_count == 1
    assert [(event.stage, event.event) for event in events] == [
        ("run", "started"),
        ("load", "started"),
        ("load", "completed"),
        ("parse", "started"),
        ("parse", "completed"),
        ("chunk", "started"),
        ("chunk", "completed"),
        ("persist", "started"),
        ("persist", "skipped"),
        ("persist", "updated"),
        ("persist", "completed"),
        ("run", "completed"),
    ]


def test_ingestor_uses_custom_logger() -> None:
    loaded_source = _loaded_source(source_uri="docs/example.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    handler = CapturingHandler()
    logger = logging.getLogger("test.docprep.ingest")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    try:
        ingestor = Ingestor(
            loader=SingleLoader(),
            parser=PassthroughParser(),
            chunkers=[],
            logger=logger,
        )
        _ = ingestor.run("ignored")
    finally:
        logger.removeHandler(handler)

    assert [record.getMessage() for record in handler.records] == [
        "Loaded 1 source(s)",
        "Parsed docs/example.md: 0 section(s)",
        "Run completed: 1 processed, 0 failed",
    ]


def test_ingestor_result_contains_stage_reports() -> None:
    loaded_source = _loaded_source(source_uri="docs/example.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    result = Ingestor(loader=SingleLoader(), parser=PassthroughParser(), chunkers=[]).run("ignored")

    stages = tuple(report.stage for report in result.stage_reports)
    assert stages == ("load", "parse", "chunk", "run")
    assert all(isinstance(report, IngestStageReport) for report in result.stage_reports)


def test_ingestor_result_contains_expanded_counts() -> None:
    loaded_source = _loaded_source(source_uri="docs/example.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    sink = RecordingSink(
        result=SinkUpsertResult(
            skipped_source_uris=(loaded_source.source_uri,),
            updated_source_uris=(),
            deleted_source_uris=(),
        )
    )

    ingestor = Ingestor(
        loader=SingleLoader(),
        parser=PassthroughParser(),
        chunkers=[],
        sink=sink,
    )
    result = ingestor.run("ignored")

    assert result.processed_count == 1
    assert result.skipped_count == 1
    assert result.updated_count == 0
    assert result.deleted_count == 0
    assert result.failed_count == 0
    assert result.skipped_source_uris == (loaded_source.source_uri,)
    assert result.updated_source_uris == ()
    assert result.deleted_source_uris == ()
    assert result.failed_source_uris == ()


def test_ingestor_records_run_manifest_to_sink_when_supported() -> None:
    loaded_source = _loaded_source(source_uri="docs/example.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    sink = RecordingSink()

    result = Ingestor(
        loader=SingleLoader(), parser=PassthroughParser(), chunkers=[], sink=sink
    ).run("ignored")

    assert result.run_manifest is not None
    assert sink.run_ids
    assert all(run_id == result.run_manifest.run_id for run_id in sink.run_ids)
    assert sink.manifests == (result.run_manifest,)
    assert result.run_manifest.scope == SourceScope(prefixes=("file:ignored/",), explicit=False)


def test_ingest_convenience_function_accepts_logger_and_progress_callback() -> None:
    loaded_source = _loaded_source(source_uri="docs/example.md")
    events: list[IngestProgressEvent] = []

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    handler = CapturingHandler()
    logger = logging.getLogger("test.docprep.ingest.convenience")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    try:
        result = ingest(
            "ignored",
            loader=SingleLoader(),
            parser=PassthroughParser(),
            chunkers=[],
            logger=logger,
            progress_callback=events.append,
        )
    finally:
        logger.removeHandler(handler)

    assert result.processed_count == 1
    assert events[0] == IngestProgressEvent(stage=PipelineStage.RUN, event="started")
    assert handler.records[-1].getMessage() == "Run completed: 1 processed, 0 failed"


def test_progress_callback_failure_raises_ingest_error() -> None:
    loaded_source = _loaded_source(source_uri="docs/example.md")

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    def failing_callback(event: IngestProgressEvent) -> None:
        if event.stage == "parse" and event.event == "started":
            raise ValueError("callback boom")

    with pytest.raises(IngestError, match="Progress callback failed"):
        Ingestor(
            loader=SingleLoader(),
            parser=PassthroughParser(),
            chunkers=[],
            progress_callback=failing_callback,
        ).run("ignored")


def test_load_failure_emits_run_failed_progress_event() -> None:
    events: list[IngestProgressEvent] = []

    with pytest.raises(IngestError, match="Loading failed"):
        Ingestor(
            loader=FailingLoader(),
            progress_callback=events.append,
        ).run("ignored")

    stage_events = [(e.stage, e.event) for e in events]
    assert ("load", "failed") in stage_events
    assert ("run", "failed") in stage_events
    run_failed = [e for e in events if e.stage == "run" and e.event == "failed"]
    assert len(run_failed) == 1
    assert run_failed[0].error_type == "RuntimeError"


def test_sink_failure_emits_run_failed_progress_event() -> None:
    loaded_source = _loaded_source(source_uri="docs/example.md")
    events: list[IngestProgressEvent] = []

    class SingleLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [loaded_source]

    class PassthroughParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return _document_from_loaded_source(loaded_source)

    class FailingSink:
        def upsert(
            self,
            documents: Sequence[Document],
            *,
            run_id: uuid.UUID | None = None,
        ) -> SinkUpsertResult:
            del documents
            del run_id
            raise RuntimeError("sink boom")

    with pytest.raises(IngestError, match="Persist failed for docs/example.md"):
        Ingestor(
            loader=SingleLoader(),
            parser=PassthroughParser(),
            chunkers=[],
            sink=FailingSink(),
            progress_callback=events.append,
            error_mode=ErrorMode.FAIL_FAST,
        ).run("ignored")

    stage_events = [(e.stage, e.event) for e in events]
    assert ("persist", "failed") in stage_events
    assert ("run", "failed") in stage_events
