"""docprep — Prepare documents into structured, vector-ready data."""

from __future__ import annotations

from collections.abc import Callable, Iterator
import importlib
import logging
from typing import cast

__version__ = "0.1.1"

from .adapters.protocol import Adapter
from .checkpoint import CheckpointStore
from .chunkers.token import TokenChunker
from .config import DocPrepConfig, ExportConfig, load_config, load_discovered_config
from .diff import compute_diff, compute_diff_from_documents
from .exceptions import (
    ChunkError,
    ConfigError,
    DocPrepError,
    IngestError,
    LoadError,
    MetadataError,
    ParseError,
    SinkError,
)
from .export import ExportDelta
from .ids import IDENTITY_VERSION, SCHEMA_VERSION, canonicalize_source_uri
from .ingest import DEFAULT_CHUNKERS, Ingestor, ingest
from .metadata import Metadata
from .models.domain import (
    Chunk,
    ChunkDelta,
    DeletePolicy,
    DeleteResult,
    DiffSummary,
    Document,
    DocumentError,
    DocumentRevision,
    ErrorMode,
    IngestResult,
    IngestStageReport,
    Page,
    PipelineStage,
    RevisionDiff,
    RunManifest,
    Section,
    SectionDelta,
    SinkUpsertResult,
    SourceScope,
    StructuralAnnotation,
    StructureKind,
    SyncResult,
    TextPrependStrategy,
    VectorRecord,
    VectorRecordV1,
)
from .progress import IngestProgressEvent, ProgressCallback
from .registry import get_all_chunkers, get_all_loaders, get_all_parsers, get_all_sinks

logging.getLogger("docprep").addHandler(logging.NullHandler())


def build_vector_records(
    documents: tuple[Document, ...],
    *,
    text_prepend: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
    include_annotations: bool = False,
) -> tuple[VectorRecord, ...]:
    export_module = importlib.import_module("docprep.export")
    build_records = cast(
        Callable[..., tuple[VectorRecord, ...]],
        getattr(export_module, "build_vector_records"),
    )
    return build_records(
        documents,
        text_prepend=text_prepend,
        include_annotations=include_annotations,
    )


def build_vector_records_v1(
    documents: tuple[Document, ...],
    *,
    text_prepend: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
    created_at: str | None = None,
    include_annotations: bool = False,
) -> tuple[VectorRecordV1, ...]:
    export_module = importlib.import_module("docprep.export")
    build_records_v1 = cast(
        Callable[..., tuple[VectorRecordV1, ...]],
        getattr(export_module, "build_vector_records_v1"),
    )
    return build_records_v1(
        documents,
        text_prepend=text_prepend,
        created_at=created_at,
        include_annotations=include_annotations,
    )


def iter_vector_records(
    documents: tuple[Document, ...],
    *,
    text_prepend: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
    include_annotations: bool = False,
) -> Iterator[VectorRecord]:
    export_module = importlib.import_module("docprep.export")
    iter_records = cast(
        Callable[..., Iterator[VectorRecord]],
        getattr(export_module, "iter_vector_records"),
    )
    return iter_records(
        documents,
        text_prepend=text_prepend,
        include_annotations=include_annotations,
    )


def iter_vector_records_v1(
    documents: tuple[Document, ...],
    *,
    text_prepend: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
    created_at: str | None = None,
    include_annotations: bool = False,
) -> Iterator[VectorRecordV1]:
    export_module = importlib.import_module("docprep.export")
    iter_records_v1 = cast(
        Callable[..., Iterator[VectorRecordV1]],
        getattr(export_module, "iter_vector_records_v1"),
    )
    return iter_records_v1(
        documents,
        text_prepend=text_prepend,
        created_at=created_at,
        include_annotations=include_annotations,
    )


def build_export_delta(
    diff_results: tuple[RevisionDiff, ...],
    documents: tuple[Document, ...],
    *,
    text_prepend: TextPrependStrategy = TextPrependStrategy.TITLE_AND_HEADING_PATH,
    created_at: str | None = None,
    include_annotations: bool = False,
) -> ExportDelta:
    export_module = importlib.import_module("docprep.export")
    build_delta = cast(
        Callable[..., ExportDelta],
        getattr(export_module, "build_export_delta"),
    )
    return build_delta(
        diff_results,
        documents,
        text_prepend=text_prepend,
        created_at=created_at,
        include_annotations=include_annotations,
    )


__all__ = [
    "__version__",
    "build_vector_records",
    "build_vector_records_v1",
    "iter_vector_records",
    "iter_vector_records_v1",
    "build_export_delta",
    "ExportDelta",
    "Adapter",
    "DEFAULT_CHUNKERS",
    "compute_diff",
    "compute_diff_from_documents",
    "ChunkDelta",
    "Chunk",
    "ChunkError",
    "ConfigError",
    "DeletePolicy",
    "DeleteResult",
    "DocPrepConfig",
    "ExportConfig",
    "DocPrepError",
    "DiffSummary",
    "Document",
    "DocumentError",
    "DocumentRevision",
    "ErrorMode",
    "canonicalize_source_uri",
    "IDENTITY_VERSION",
    "SCHEMA_VERSION",
    "get_all_chunkers",
    "get_all_loaders",
    "get_all_parsers",
    "get_all_sinks",
    "ingest",
    "IngestError",
    "IngestProgressEvent",
    "Ingestor",
    "IngestResult",
    "IngestStageReport",
    "Page",
    "PipelineStage",
    "RevisionDiff",
    "load_config",
    "load_discovered_config",
    "LoadError",
    "Metadata",
    "MetadataError",
    "ParseError",
    "ProgressCallback",
    "RunManifest",
    "SectionDelta",
    "Section",
    "SinkError",
    "SinkUpsertResult",
    "SourceScope",
    "StructuralAnnotation",
    "StructureKind",
    "SyncResult",
    "TextPrependStrategy",
    "TokenChunker",
    "CheckpointStore",
    "VectorRecord",
    "VectorRecordV1",
]
