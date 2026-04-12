"""Ingestor — orchestrates the document ingestion pipeline."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import logging
from pathlib import Path
import time
import uuid

from .chunkers.heading import HeadingChunker
from .chunkers.protocol import Chunker
from .chunkers.size import SizeChunker
from .config import DocPrepConfig
from .exceptions import ConfigError, IngestError
from .loaders.protocol import Loader
from .models.domain import (
    Document,
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

DEFAULT_CHUNKERS: Sequence[Chunker] = (HeadingChunker(), SizeChunker())
"""Canonical default chunker pipeline — used by both Ingestor and CLI.

Provides heading-based sectioning followed by token-size splitting.
"""


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

    def _emit(self, event: IngestProgressEvent) -> None:
        if self._progress_callback is not None:
            try:
                self._progress_callback(event)
            except Exception as exc:
                raise IngestError(
                    f"Progress callback failed on {event.stage}.{event.event}: {exc}"
                ) from exc

    def run(self, source: str | Path | None = None) -> IngestResult:
        run_start = time.perf_counter()
        self._emit(IngestProgressEvent(stage=PipelineStage.RUN, event="started"))

        resolved_source = self._resolve_source(source)
        run_scope = self._scope if self._scope is not None else derive_scope(resolved_source)

        # --- Load stage ---
        load_start = time.perf_counter()
        self._emit(IngestProgressEvent(stage=PipelineStage.LOAD, event="started"))
        try:
            loaded_sources = list(self._loader.load(resolved_source))
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

        # --- Parse + Chunk stages (per-source, best-effort) ---
        documents: list[Document] = []
        parse_failed_uris: list[str] = []
        chunk_failed_uris: list[str] = []
        parse_start = time.perf_counter()
        chunk_elapsed_total = 0.0
        parsed_count = 0

        for idx, ls in enumerate(loaded_sources):
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
                parse_failed_uris.append(ls.source_uri)
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
                chunk_failed_uris.append(ls.source_uri)
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

        parse_elapsed = (time.perf_counter() - parse_start) * 1000 - chunk_elapsed_total
        parse_report = IngestStageReport(
            stage=PipelineStage.PARSE,
            elapsed_ms=parse_elapsed,
            input_count=len(loaded_sources),
            output_count=parsed_count,
            failed_count=len(parse_failed_uris),
        )
        chunk_report = IngestStageReport(
            stage=PipelineStage.CHUNK,
            elapsed_ms=chunk_elapsed_total,
            input_count=parsed_count,
            output_count=len(documents),
            failed_count=len(chunk_failed_uris),
        )

        all_failed_uris = parse_failed_uris + chunk_failed_uris

        # --- Sink stage ---
        sink_result = SinkUpsertResult()
        persisted = False
        sink_name: str | None = None
        sink_report: IngestStageReport | None = None

        run_manifest = RunManifest(
            run_id=uuid.uuid4(),
            scope=run_scope,
            source_uris_seen=tuple(ls.source_uri for ls in loaded_sources),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        if self._sink is not None:
            sink_start = time.perf_counter()
            sink_name = type(self._sink).__name__
            self._emit(
                IngestProgressEvent(
                    stage=PipelineStage.PERSIST, event="started", sink_name=sink_name
                )
            )
            try:
                sink_result = self._sink.upsert(documents, run_id=run_manifest.run_id)
                record_run = getattr(self._sink, "record_run", None)
                if callable(record_run):
                    _ = record_run(run_manifest)
                persisted = True
            except Exception as exc:
                self._logger.error(
                    "Sink failed: %s",
                    type(exc).__name__,
                    extra={
                        "stage": PipelineStage.PERSIST,
                        "event": "failed",
                        "sink_name": sink_name,
                        "error_type": type(exc).__name__,
                    },
                )
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.PERSIST,
                        event="failed",
                        sink_name=sink_name,
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
                raise IngestError(f"Sink failed: {exc}") from exc
            sink_elapsed = (time.perf_counter() - sink_start) * 1000

            for uri in sink_result.skipped_source_uris:
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.PERSIST, event="skipped", source_uri=uri
                    )
                )
            for uri in sink_result.updated_source_uris:
                self._emit(
                    IngestProgressEvent(
                        stage=PipelineStage.PERSIST, event="updated", source_uri=uri
                    )
                )

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

        # --- Run report ---
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
            failed_count=len(all_failed_uris),
        )
        stage_reports_list.append(run_report)

        self._logger.info(
            "Run completed: %d processed, %d failed",
            len(documents),
            len(all_failed_uris),
            extra={
                "stage": PipelineStage.RUN,
                "event": "completed",
                "processed_count": len(documents),
                "failed_count": len(all_failed_uris),
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

        return IngestResult(
            documents=tuple(documents),
            processed_count=len(documents),
            skipped_count=len(sink_result.skipped_source_uris),
            updated_count=len(sink_result.updated_source_uris),
            deleted_count=0,
            failed_count=len(all_failed_uris),
            skipped_source_uris=sink_result.skipped_source_uris,
            updated_source_uris=sink_result.updated_source_uris,
            deleted_source_uris=(),
            failed_source_uris=tuple(all_failed_uris),
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
        from .loaders.markdown import MarkdownLoader

        return MarkdownLoader()

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
    ).run(source)
