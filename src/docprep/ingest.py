"""Ingestor — orchestrates the document ingestion pipeline."""

from __future__ import annotations

from collections.abc import Sequence
import concurrent.futures
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
import time
from typing import TYPE_CHECKING
import uuid

from .chunkers.heading import HeadingChunker
from .chunkers.protocol import Chunker
from .chunkers.size import SizeChunker
from .config import DocPrepConfig
from .exceptions import ConfigError, IngestError
from .loaders.protocol import Loader
from .loaders.types import LoadedSource
from .models.domain import (
    Document,
    DocumentError,
    ErrorMode,
    IngestResult,
    IngestStageReport,
    PipelineStage,
    RunManifest,
    SinkUpsertResult,
    SourceScope,
)
from .parsers.protocol import Parser
from .progress import IngestProgressEvent, ProgressCallback
from .scope import derive_scope
from .sinks.protocol import Sink

if TYPE_CHECKING:
    from .checkpoint import CheckpointStore

DEFAULT_CHUNKERS: Sequence[Chunker] = (HeadingChunker(), SizeChunker())
"""Canonical default chunker pipeline — used by both Ingestor and CLI.

Provides heading-based sectioning followed by character-budget splitting.
"""


@dataclass(frozen=True)
class _ParseChunkSuccess:
    index: int
    document: Document
    parse_elapsed_ms: float
    chunk_elapsed_ms: float


@dataclass(frozen=True)
class _ParseChunkFailure:
    index: int
    source_uri: str
    errors: list[DocumentError]
    parse_elapsed_ms: float
    chunk_elapsed_ms: float
    sections_count: int | None = None


def _parse_and_chunk(
    index: int,
    loaded_source: LoadedSource,
    parser: Parser,
    chunkers: Sequence[Chunker],
) -> _ParseChunkSuccess | _ParseChunkFailure:
    parse_start = time.perf_counter()
    try:
        parsed = parser.parse(loaded_source)
    except Exception as exc:
        parse_elapsed_ms = (time.perf_counter() - parse_start) * 1000
        return _ParseChunkFailure(
            index=index,
            source_uri=loaded_source.source_uri,
            errors=[
                DocumentError(
                    source_uri=loaded_source.source_uri,
                    stage=PipelineStage.PARSE,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            ],
            parse_elapsed_ms=parse_elapsed_ms,
            chunk_elapsed_ms=0.0,
        )

    parse_elapsed_ms = (time.perf_counter() - parse_start) * 1000
    chunk_start = time.perf_counter()
    try:
        chunked = parsed
        for chunker in chunkers:
            chunked = chunker.chunk(chunked)
    except Exception as exc:
        chunk_elapsed_ms = (time.perf_counter() - chunk_start) * 1000
        return _ParseChunkFailure(
            index=index,
            source_uri=loaded_source.source_uri,
            errors=[
                DocumentError(
                    source_uri=loaded_source.source_uri,
                    stage=PipelineStage.CHUNK,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            ],
            parse_elapsed_ms=parse_elapsed_ms,
            chunk_elapsed_ms=chunk_elapsed_ms,
            sections_count=len(parsed.sections),
        )

    chunk_elapsed_ms = (time.perf_counter() - chunk_start) * 1000
    return _ParseChunkSuccess(
        index=index,
        document=chunked,
        parse_elapsed_ms=parse_elapsed_ms,
        chunk_elapsed_ms=chunk_elapsed_ms,
    )


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
        scope: SourceScope | None = None,
        logger: logging.Logger | None = None,
        progress_callback: ProgressCallback | None = None,
        error_mode: ErrorMode = ErrorMode.CONTINUE_ON_ERROR,
    ) -> None:
        self._config = config
        self._loader = loader if loader is not None else self._loader_from_config(config)
        self._parser = parser if parser is not None else self._parser_from_config(config)
        self._chunkers: Sequence[Chunker] = (
            chunkers if chunkers is not None else self._chunkers_from_config(config)
        )
        self._sink = sink if sink is not None else self._sink_from_config(config)
        self._scope = scope
        self._logger = logger if logger is not None else logging.getLogger("docprep.ingest")
        self._progress_callback = progress_callback
        self._error_mode = error_mode

    def _emit(self, event: IngestProgressEvent) -> None:
        if self._progress_callback is not None:
            try:
                self._progress_callback(event)
            except Exception as exc:
                raise IngestError(
                    f"Progress callback failed on {event.stage}.{event.event}: {exc}"
                ) from exc

    def run(
        self,
        source: str | Path | None = None,
        workers: int = 1,
        resume: bool = False,
        checkpoint_path: str | Path | None = None,
    ) -> IngestResult:
        run_start = time.perf_counter()
        self._emit(IngestProgressEvent(stage=PipelineStage.RUN, event="started"))

        if workers < 1:
            raise IngestError("workers must be >= 1")

        resolved_source = self._resolve_source(source)
        run_scope = self._scope if self._scope is not None else derive_scope(resolved_source)

        loaded_sources, load_report = self._run_load_stage(resolved_source)
        checkpoint, checkpoint_skipped_source_uris, run_id, run_id_text = self._setup_checkpoint(
            resume=resume,
            checkpoint_path=checkpoint_path,
        )
        documents, errors, parsed_count, parse_report, chunk_elapsed_total = self._run_parse_stage(
            loaded_sources=loaded_sources,
            workers=workers,
            checkpoint=checkpoint,
            checkpoint_skipped_source_uris=checkpoint_skipped_source_uris,
            run_id_text=run_id_text,
        )
        chunk_report = self._run_chunk_stage(
            parsed_count=parsed_count,
            documents=documents,
            errors=errors,
            chunk_elapsed_total=chunk_elapsed_total,
        )

        run_manifest = RunManifest(
            run_id=run_id,
            scope=run_scope,
            source_uris_seen=tuple(ls.source_uri for ls in loaded_sources),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        sink_result, persisted, sink_name, sink_report = self._run_persist_stage(
            documents=documents,
            errors=errors,
            checkpoint=checkpoint,
            run_id_text=run_id_text,
            run_manifest=run_manifest,
        )
        return self._build_result(
            run_start=run_start,
            loaded_sources=loaded_sources,
            documents=documents,
            errors=errors,
            load_report=load_report,
            parse_report=parse_report,
            chunk_report=chunk_report,
            sink_report=sink_report,
            checkpoint=checkpoint,
            checkpoint_skipped_source_uris=checkpoint_skipped_source_uris,
            sink_result=sink_result,
            persisted=persisted,
            sink_name=sink_name,
            run_manifest=run_manifest,
            run_id_text=run_id_text,
        )

    def _run_load_stage(self, source: str | Path) -> tuple[list[LoadedSource], IngestStageReport]:
        load_start = time.perf_counter()
        self._emit(IngestProgressEvent(stage=PipelineStage.LOAD, event="started"))
        try:
            loaded_sources = list(self._loader.load(source))
        except Exception as exc:
            self._logger.error(
                "Load stage failed: %s",
                type(exc).__name__,
                extra={
                    "stage": PipelineStage.LOAD,
                    "event": "failed",
                    "error_type": type(exc).__name__,
                },
            )
            self._emit(
                IngestProgressEvent(
                    stage=PipelineStage.LOAD,
                    event="failed",
                    error_type=type(exc).__name__,
                )
            )
            self._emit(
                IngestProgressEvent(
                    stage=PipelineStage.RUN,
                    event="failed",
                    error_type=type(exc).__name__,
                )
            )
            raise IngestError(f"Loading failed: {exc}") from exc

        load_elapsed = (time.perf_counter() - load_start) * 1000
        self._logger.info(
            "Loaded %d source(s)",
            len(loaded_sources),
            extra={"stage": PipelineStage.LOAD, "event": "completed", "count": len(loaded_sources)},
        )
        self._emit(
            IngestProgressEvent(
                stage=PipelineStage.LOAD,
                event="completed",
                total=len(loaded_sources),
                elapsed_ms=load_elapsed,
            )
        )
        load_report = IngestStageReport(
            stage=PipelineStage.LOAD,
            elapsed_ms=load_elapsed,
            output_count=len(loaded_sources),
        )
        return loaded_sources, load_report

    def _setup_checkpoint(
        self,
        *,
        resume: bool,
        checkpoint_path: str | Path | None,
    ) -> tuple[CheckpointStore | None, list[str], uuid.UUID, str]:
        checkpoint: CheckpointStore | None = None
        checkpoint_skipped_source_uris: list[str] = []
        run_id = uuid.uuid4()
        run_id_text = str(run_id)
        if resume:
            from .checkpoint import CheckpointStore, compute_config_fingerprint

            checkpoint = CheckpointStore(path=checkpoint_path)
            config_fp = compute_config_fingerprint(
                loader_config=self._config.loader if self._config else None,
                parser_config=self._config.parser if self._config else None,
                chunker_configs=self._config.chunkers if self._config else None,
            )
            checkpoint.load(config_fp)
        return checkpoint, checkpoint_skipped_source_uris, run_id, run_id_text

    def _run_parse_stage(
        self,
        *,
        loaded_sources: list[LoadedSource],
        workers: int,
        checkpoint: CheckpointStore | None,
        checkpoint_skipped_source_uris: list[str],
        run_id_text: str,
    ) -> tuple[list[Document], list[DocumentError], int, IngestStageReport, float]:
        documents: list[Document] = []
        errors: list[DocumentError] = []
        parse_start = time.perf_counter()
        parse_elapsed_total = 0.0
        chunk_elapsed_total = 0.0
        parsed_count = 0

        if workers == 1:
            for idx, ls in enumerate(loaded_sources):
                if checkpoint is not None and checkpoint.is_completed(ls.source_uri, ls.checksum):
                    self._emit(
                        IngestProgressEvent(
                            stage=PipelineStage.PARSE,
                            event="skipped",
                            source_uri=ls.source_uri,
                            current=idx + 1,
                            total=len(loaded_sources),
                        )
                    )
                    checkpoint_skipped_source_uris.append(ls.source_uri)
                    continue
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.PARSE,
                        event="started",
                        source_uri=ls.source_uri,
                        current=idx + 1,
                        total=len(loaded_sources),
                    )
                )
                try:
                    doc = self._parser.parse(ls)
                except Exception as exc:
                    error = DocumentError(
                        source_uri=ls.source_uri,
                        stage=PipelineStage.PARSE,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                    errors.append(error)
                    self._logger.warning(
                        "Parse failed for %s: %s",
                        ls.source_uri,
                        type(exc).__name__,
                        extra={
                            "stage": PipelineStage.PARSE,
                            "event": "failed",
                            "source_uri": ls.source_uri,
                            "error_type": type(exc).__name__,
                        },
                    )
                    self._emit(
                        IngestProgressEvent(
                            stage=PipelineStage.PARSE,
                            event="failed",
                            source_uri=ls.source_uri,
                            error_type=type(exc).__name__,
                        )
                    )
                    if self._error_mode == ErrorMode.FAIL_FAST:
                        self._emit(
                            IngestProgressEvent(
                                stage=PipelineStage.RUN,
                                event="failed",
                                error_type=type(exc).__name__,
                            )
                        )
                        raise IngestError(f"parse failed for {ls.source_uri}: {exc}") from exc
                    continue

                parsed_count += 1
                self._logger.debug(
                    "Parsed %s: %d section(s)",
                    ls.source_uri,
                    len(doc.sections),
                    extra={
                        "stage": PipelineStage.PARSE,
                        "event": "completed",
                        "source_uri": ls.source_uri,
                        "sections_count": len(doc.sections),
                    },
                )
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.PARSE,
                        event="completed",
                        source_uri=ls.source_uri,
                        sections_count=len(doc.sections),
                    )
                )

                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.CHUNK,
                        event="started",
                        source_uri=ls.source_uri,
                    )
                )
                chunk_start = time.perf_counter()
                try:
                    for chunker in self._chunkers:
                        doc = chunker.chunk(doc)
                except Exception as exc:
                    chunk_elapsed_total += (time.perf_counter() - chunk_start) * 1000
                    error = DocumentError(
                        source_uri=ls.source_uri,
                        stage=PipelineStage.CHUNK,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                    errors.append(error)
                    self._logger.warning(
                        "Chunk failed for %s: %s",
                        ls.source_uri,
                        type(exc).__name__,
                        extra={
                            "stage": PipelineStage.CHUNK,
                            "event": "failed",
                            "source_uri": ls.source_uri,
                            "error_type": type(exc).__name__,
                        },
                    )
                    self._emit(
                        IngestProgressEvent(
                            stage=PipelineStage.CHUNK,
                            event="failed",
                            source_uri=ls.source_uri,
                            error_type=type(exc).__name__,
                        )
                    )
                    if self._error_mode == ErrorMode.FAIL_FAST:
                        self._emit(
                            IngestProgressEvent(
                                stage=PipelineStage.RUN,
                                event="failed",
                                error_type=type(exc).__name__,
                            )
                        )
                        raise IngestError(f"chunk failed for {ls.source_uri}: {exc}") from exc
                    continue
                chunk_elapsed_total += (time.perf_counter() - chunk_start) * 1000

                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.CHUNK,
                        event="completed",
                        source_uri=ls.source_uri,
                        chunks_count=len(doc.chunks),
                    )
                )
                documents.append(doc)
            parse_elapsed_total = (time.perf_counter() - parse_start) * 1000 - chunk_elapsed_total
        else:
            sources_to_process: list[tuple[int, LoadedSource]] = []
            for idx, ls in enumerate(loaded_sources):
                if checkpoint is not None and checkpoint.is_completed(ls.source_uri, ls.checksum):
                    self._emit(
                        IngestProgressEvent(
                            stage=PipelineStage.PARSE,
                            event="skipped",
                            source_uri=ls.source_uri,
                            current=idx + 1,
                            total=len(loaded_sources),
                        )
                    )
                    checkpoint_skipped_source_uris.append(ls.source_uri)
                    continue
                sources_to_process.append((idx, ls))

            future_to_indexed_source: dict[
                Future[_ParseChunkSuccess | _ParseChunkFailure],
                tuple[int, LoadedSource],
            ] = {}
            pending_futures: set[Future[_ParseChunkSuccess | _ParseChunkFailure]] = set()
            unordered_results: list[_ParseChunkSuccess | _ParseChunkFailure] = []

            with ThreadPoolExecutor(max_workers=workers) as executor:
                for idx, ls in sources_to_process:
                    future = executor.submit(
                        _parse_and_chunk,
                        idx,
                        ls,
                        self._parser,
                        self._chunkers,
                    )
                    future_to_indexed_source[future] = (idx, ls)
                    pending_futures.add(future)

                for future in concurrent.futures.as_completed(future_to_indexed_source):
                    pending_futures.discard(future)
                    try:
                        unordered_results.append(future.result())
                    except Exception as exc:
                        idx, loaded_source = future_to_indexed_source[future]
                        unordered_results.append(
                            _ParseChunkFailure(
                                index=idx,
                                source_uri=loaded_source.source_uri,
                                errors=[
                                    DocumentError(
                                        source_uri=loaded_source.source_uri,
                                        stage=PipelineStage.PARSE,
                                        error_type=type(exc).__name__,
                                        message=str(exc),
                                    )
                                ],
                                parse_elapsed_ms=0.0,
                                chunk_elapsed_ms=0.0,
                            )
                        )

            ordered_results = sorted(unordered_results, key=lambda result: result.index)

            for result in ordered_results:
                if isinstance(result, _ParseChunkSuccess):
                    source_uri = result.document.source_uri
                else:
                    source_uri = result.source_uri

                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.PARSE,
                        event="started",
                        source_uri=source_uri,
                        current=result.index + 1,
                        total=len(loaded_sources),
                    )
                )

                if isinstance(result, _ParseChunkFailure):
                    parse_elapsed_total += result.parse_elapsed_ms
                    chunk_elapsed_total += result.chunk_elapsed_ms
                    error = result.errors[0]
                    errors.extend(result.errors)

                    if error.stage == PipelineStage.PARSE:
                        self._logger.warning(
                            "Parse failed for %s: %s",
                            result.source_uri,
                            error.error_type,
                            extra={
                                "stage": PipelineStage.PARSE,
                                "event": "failed",
                                "source_uri": result.source_uri,
                                "error_type": error.error_type,
                            },
                        )
                        self._emit(
                            IngestProgressEvent(
                                stage=PipelineStage.PARSE,
                                event="failed",
                                source_uri=result.source_uri,
                                error_type=error.error_type,
                            )
                        )
                        if self._error_mode == ErrorMode.FAIL_FAST:
                            for future in pending_futures:
                                _ = future.cancel()
                            self._emit(
                                IngestProgressEvent(
                                    stage=PipelineStage.RUN,
                                    event="failed",
                                    error_type=error.error_type,
                                )
                            )
                            raise IngestError(
                                f"parse failed for {result.source_uri}: {error.message}"
                            )
                        continue

                    parsed_count += 1
                    if result.sections_count is not None:
                        self._logger.debug(
                            "Parsed %s: %d section(s)",
                            result.source_uri,
                            result.sections_count,
                            extra={
                                "stage": PipelineStage.PARSE,
                                "event": "completed",
                                "source_uri": result.source_uri,
                                "sections_count": result.sections_count,
                            },
                        )
                    self._emit(
                        IngestProgressEvent(
                            stage=PipelineStage.PARSE,
                            event="completed",
                            source_uri=result.source_uri,
                            sections_count=result.sections_count,
                        )
                    )
                    self._emit(
                        IngestProgressEvent(
                            stage=PipelineStage.CHUNK,
                            event="started",
                            source_uri=result.source_uri,
                        )
                    )
                    self._logger.warning(
                        "Chunk failed for %s: %s",
                        result.source_uri,
                        error.error_type,
                        extra={
                            "stage": PipelineStage.CHUNK,
                            "event": "failed",
                            "source_uri": result.source_uri,
                            "error_type": error.error_type,
                        },
                    )
                    self._emit(
                        IngestProgressEvent(
                            stage=PipelineStage.CHUNK,
                            event="failed",
                            source_uri=result.source_uri,
                            error_type=error.error_type,
                        )
                    )
                    if self._error_mode == ErrorMode.FAIL_FAST:
                        for future in pending_futures:
                            _ = future.cancel()
                        self._emit(
                            IngestProgressEvent(
                                stage=PipelineStage.RUN,
                                event="failed",
                                error_type=error.error_type,
                            )
                        )
                        raise IngestError(f"chunk failed for {result.source_uri}: {error.message}")
                    continue

                parsed_count += 1
                parse_elapsed_total += result.parse_elapsed_ms
                chunk_elapsed_total += result.chunk_elapsed_ms
                self._logger.debug(
                    "Parsed %s: %d section(s)",
                    result.document.source_uri,
                    len(result.document.sections),
                    extra={
                        "stage": PipelineStage.PARSE,
                        "event": "completed",
                        "source_uri": result.document.source_uri,
                        "sections_count": len(result.document.sections),
                    },
                )
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.PARSE,
                        event="completed",
                        source_uri=result.document.source_uri,
                        sections_count=len(result.document.sections),
                    )
                )
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.CHUNK,
                        event="started",
                        source_uri=result.document.source_uri,
                    )
                )
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.CHUNK,
                        event="completed",
                        source_uri=result.document.source_uri,
                        chunks_count=len(result.document.chunks),
                    )
                )
                documents.append(result.document)

        parse_failed_uris = [
            error.source_uri for error in errors if error.stage == PipelineStage.PARSE
        ]
        parse_report = IngestStageReport(
            stage=PipelineStage.PARSE,
            elapsed_ms=parse_elapsed_total,
            input_count=len(loaded_sources),
            output_count=parsed_count,
            failed_count=len(parse_failed_uris),
        )
        return documents, errors, parsed_count, parse_report, chunk_elapsed_total

    def _run_chunk_stage(
        self,
        *,
        parsed_count: int,
        documents: list[Document],
        errors: list[DocumentError],
        chunk_elapsed_total: float,
    ) -> IngestStageReport:
        chunk_failed_uris = [
            error.source_uri for error in errors if error.stage == PipelineStage.CHUNK
        ]
        return IngestStageReport(
            stage=PipelineStage.CHUNK,
            elapsed_ms=chunk_elapsed_total,
            input_count=parsed_count,
            output_count=len(documents),
            failed_count=len(chunk_failed_uris),
        )

    def _run_persist_stage(
        self,
        *,
        documents: list[Document],
        errors: list[DocumentError],
        checkpoint: CheckpointStore | None,
        run_id_text: str,
        run_manifest: RunManifest,
    ) -> tuple[SinkUpsertResult, bool, str | None, IngestStageReport | None]:
        """Persist documents to the configured sink.

        Ingest is additive-only by design: it upserts documents but never deletes.
        To remove stale documents, use the separate ``prune`` command or
        ``sink.sync()`` API. This separation ensures ingest runs are safe to
        retry and never accidentally delete data.
        """
        sink_result = SinkUpsertResult()
        persisted = False
        sink_name: str | None = None
        sink_report: IngestStageReport | None = None
        if self._sink is None:
            # No sink configured — checkpoint all parsed documents since there's
            # nothing to persist (can't fail).
            if checkpoint is not None and documents:
                for doc in documents:
                    checkpoint.mark_completed(doc.source_uri, doc.source_checksum)
                checkpoint.save(run_id_text)
            return sink_result, persisted, sink_name, sink_report

        sink_start = time.perf_counter()
        sink_name = type(self._sink).__name__
        self._emit(
            IngestProgressEvent(
                stage=PipelineStage.PERSIST,
                event="started",
                sink_name=sink_name,
            )
        )
        sink_result_skipped: list[str] = []
        sink_result_updated: list[str] = []
        upsert_succeeded = False
        try:
            batch_result = self._sink.upsert(documents, run_id=run_manifest.run_id)
            sink_result_skipped.extend(batch_result.skipped_source_uris)
            sink_result_updated.extend(batch_result.updated_source_uris)

            # Emit per-document progress events for skipped documents
            for uri in batch_result.skipped_source_uris:
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.PERSIST,
                        event="skipped",
                        source_uri=uri,
                    )
                )

            # Emit per-document progress events for updated documents
            for uri in batch_result.updated_source_uris:
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.PERSIST,
                        event="updated",
                        source_uri=uri,
                    )
                )
            upsert_succeeded = True
            # Checkpoint after successful persist so unpersisted docs are
            # re-processed on resume (fixes #69).
            if checkpoint is not None:
                for doc in documents:
                    checkpoint.mark_completed(doc.source_uri, doc.source_checksum)
                checkpoint.save(run_id_text)
        except Exception as exc:
            for doc in documents:
                error = DocumentError(
                    source_uri=doc.source_uri,
                    stage=PipelineStage.PERSIST,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
                errors.append(error)
                self._logger.error(
                    "Persist failed for %s: %s: %s",
                    doc.source_uri,
                    type(exc).__name__,
                    exc,
                    extra={
                        "stage": PipelineStage.PERSIST,
                        "event": "failed",
                        "sink_name": sink_name,
                        "source_uri": doc.source_uri,
                        "error_type": type(exc).__name__,
                    },
                )
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.PERSIST,
                        event="failed",
                        sink_name=sink_name,
                        source_uri=doc.source_uri,
                        error_type=type(exc).__name__,
                    )
                )
            if self._error_mode == ErrorMode.FAIL_FAST:
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.RUN,
                        event="failed",
                        error_type=type(exc).__name__,
                    )
                )
                raise IngestError(
                    f"Persist failed for {len(documents)} document(s): {exc}"
                ) from exc

        sink_result = SinkUpsertResult(
            skipped_source_uris=tuple(sink_result_skipped),
            updated_source_uris=tuple(sink_result_updated),
        )

        if documents and upsert_succeeded:
            record_run = getattr(self._sink, "record_run", None)
            if callable(record_run):
                _ = record_run(run_manifest)
            persisted = True

        sink_elapsed = (time.perf_counter() - sink_start) * 1000
        self._logger.info(
            "Sink completed: %d updated, %d skipped",
            len(sink_result.updated_source_uris),
            len(sink_result.skipped_source_uris),
            extra={
                "stage": PipelineStage.PERSIST,
                "event": "completed",
                "sink_name": sink_name,
                "updated_count": len(sink_result.updated_source_uris),
                "skipped_count": len(sink_result.skipped_source_uris),
            },
        )
        self._emit(
            IngestProgressEvent(
                stage=PipelineStage.PERSIST,
                event="completed",
                sink_name=sink_name,
                elapsed_ms=sink_elapsed,
            )
        )
        sink_report = IngestStageReport(
            stage=PipelineStage.PERSIST,
            elapsed_ms=sink_elapsed,
            input_count=len(documents),
            output_count=len(sink_result.updated_source_uris)
            + len(sink_result.skipped_source_uris),
        )
        return sink_result, persisted, sink_name, sink_report

    def _build_result(
        self,
        *,
        run_start: float,
        loaded_sources: list[LoadedSource],
        documents: list[Document],
        errors: list[DocumentError],
        load_report: IngestStageReport,
        parse_report: IngestStageReport,
        chunk_report: IngestStageReport,
        sink_report: IngestStageReport | None,
        checkpoint: CheckpointStore | None,
        checkpoint_skipped_source_uris: list[str],
        sink_result: SinkUpsertResult,
        persisted: bool,
        sink_name: str | None,
        run_manifest: RunManifest,
        run_id_text: str,
    ) -> IngestResult:
        run_elapsed = (time.perf_counter() - run_start) * 1000
        stage_reports_list: list[IngestStageReport] = [
            load_report,
            parse_report,
            chunk_report,
        ]
        if sink_report is not None:
            stage_reports_list.append(sink_report)

        run_report = IngestStageReport(
            stage=PipelineStage.RUN,
            elapsed_ms=run_elapsed,
            input_count=len(loaded_sources),
            output_count=len(documents),
            failed_count=len(errors),
        )
        stage_reports_list.append(run_report)

        self._logger.info(
            "Run completed: %d processed, %d failed",
            len(documents),
            len(errors),
            extra={
                "stage": PipelineStage.RUN,
                "event": "completed",
                "processed_count": len(documents),
                "failed_count": len(errors),
            },
        )
        self._emit(
            IngestProgressEvent(
                stage=PipelineStage.RUN,
                event="completed",
                total=len(loaded_sources),
                elapsed_ms=run_elapsed,
            )
        )

        if checkpoint is not None:
            checkpoint.save(run_id_text)

        all_failed_uris = [error.source_uri for error in errors]
        skipped_source_uris = (
            tuple(checkpoint_skipped_source_uris) + sink_result.skipped_source_uris
        )

        return IngestResult(
            documents=tuple(documents),
            processed_count=len(documents),
            skipped_count=len(skipped_source_uris),
            updated_count=len(sink_result.updated_source_uris),
            deleted_count=0,
            failed_count=len(all_failed_uris),
            skipped_source_uris=skipped_source_uris,
            updated_source_uris=sink_result.updated_source_uris,
            deleted_source_uris=(),
            failed_source_uris=tuple(all_failed_uris),
            errors=tuple(errors),
            stage_reports=tuple(stage_reports_list),
            persisted=persisted,
            sink_name=sink_name,
            run_manifest=run_manifest,
        )

    def _resolve_source(self, source: str | Path | None) -> str | Path:
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
            from .registry import build_loader

            return build_loader(config.loader)
        from .loaders.filesystem import FileSystemLoader

        return FileSystemLoader()

    @staticmethod
    def _parser_from_config(config: DocPrepConfig | None) -> Parser:
        if config is not None and config.parser is not None:
            from .registry import build_parser

            return build_parser(config.parser)
        from .parsers.multi import MultiFormatParser

        return MultiFormatParser()

    @staticmethod
    def _chunkers_from_config(config: DocPrepConfig | None) -> Sequence[Chunker]:
        if config is not None and config.chunkers is not None:
            from .registry import build_chunkers

            return build_chunkers(config.chunkers)
        return DEFAULT_CHUNKERS

    @staticmethod
    def _sink_from_config(config: DocPrepConfig | None) -> Sink | None:
        if config is not None and config.sink is not None:
            from .registry import build_sink

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
    scope: SourceScope | None = None,
    logger: logging.Logger | None = None,
    progress_callback: ProgressCallback | None = None,
    error_mode: ErrorMode = ErrorMode.CONTINUE_ON_ERROR,
    workers: int = 1,
    resume: bool = False,
    checkpoint_path: str | Path | None = None,
) -> IngestResult:
    return Ingestor(
        config=config,
        loader=loader,
        parser=parser,
        chunkers=chunkers,
        sink=sink,
        scope=scope,
        logger=logger,
        progress_callback=progress_callback,
        error_mode=error_mode,
    ).run(
        source,
        workers=workers,
        resume=resume,
        checkpoint_path=checkpoint_path,
    )
