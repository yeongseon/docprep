"""Chunker protocol — splits documents into sections and chunks."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from docprep.models.domain import Document


@runtime_checkable
class Chunker(Protocol):
    """Splits a document into sections or chunks."""

    def chunk(self, document: Document) -> Document: ...
