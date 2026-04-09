"""docprep — Prepare documents into structured, vector-ready data."""

from __future__ import annotations

__version__ = "0.0.1"

from docprep.config import DocPrepConfig, load_config, load_discovered_config
from docprep.exceptions import (
    ChunkError,
    ConfigError,
    DocPrepError,
    IngestError,
    LoadError,
    MetadataError,
    ParseError,
    SinkError,
)
from docprep.export import build_vector_records
from docprep.ingest import Ingestor, ingest
from docprep.metadata import Metadata
from docprep.models.domain import Chunk, Document, IngestResult, Section, VectorRecord

__all__ = [
    "__version__",
    "build_vector_records",
    "Chunk",
    "ChunkError",
    "ConfigError",
    "DocPrepConfig",
    "DocPrepError",
    "Document",
    "ingest",
    "IngestError",
    "Ingestor",
    "IngestResult",
    "load_config",
    "load_discovered_config",
    "LoadError",
    "Metadata",
    "MetadataError",
    "ParseError",
    "Section",
    "SinkError",
    "VectorRecord",
]
