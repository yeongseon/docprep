"""docprep exception hierarchy."""

from __future__ import annotations


class DocPrepError(Exception):
    """Base exception for all docprep errors."""


class LoadError(DocPrepError):
    """Raised when a source cannot be loaded."""


class ParseError(DocPrepError):
    """Raised when a loaded source cannot be parsed."""


class ChunkError(DocPrepError):
    """Raised when chunking fails."""


class SinkError(DocPrepError):
    """Raised when a sink operation fails."""


class IngestError(DocPrepError):
    """Raised when the ingest pipeline encounters an error."""
