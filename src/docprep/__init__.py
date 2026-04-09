"""docprep — Prepare documents into structured, vector-ready data."""

from __future__ import annotations

__version__ = "0.0.1"

from docprep.exceptions import (
    ChunkError,
    DocPrepError,
    IngestError,
    LoadError,
    ParseError,
    SinkError,
)
from docprep.export import build_vector_records
from docprep.ingest import Ingestor, ingest
from docprep.models.domain import Chunk, Document, IngestResult, Section, VectorRecord

__all__ = [
    "__version__",
    "build_vector_records",
    "Chunk",
    "ChunkError",
    "DocPrepError",
    "Document",
    "ingest",
    "IngestError",
    "Ingestor",
    "IngestResult",
    "LoadError",
    "ParseError",
    "Section",
    "SinkError",
    "VectorRecord",
]
