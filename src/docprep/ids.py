"""Deterministic ID generation and checksum utilities."""

from __future__ import annotations

import hashlib
import uuid

# Docprep namespace for UUIDv5 — generated once, stable forever.
DOCPREP_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def document_id(source_uri: str) -> uuid.UUID:
    """Generate a deterministic document ID from a source URI."""
    return uuid.uuid5(DOCPREP_NAMESPACE, source_uri)


def section_id(doc_id: uuid.UUID, order_index: int) -> uuid.UUID:
    """Generate a deterministic section ID from document ID and order index."""
    return uuid.uuid5(DOCPREP_NAMESPACE, f"{doc_id}:section:{order_index}")


def chunk_id(sect_id: uuid.UUID, section_chunk_index: int) -> uuid.UUID:
    """Generate a deterministic chunk ID from section ID and chunk index."""
    return uuid.uuid5(DOCPREP_NAMESPACE, f"{sect_id}:chunk:{section_chunk_index}")


def sha256_checksum(content: str) -> str:
    """Compute SHA-256 hex digest of a string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
