"""Sink protocol — persists documents to storage."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from docprep.models.domain import Document


@runtime_checkable
class Sink(Protocol):
    """Persists documents to a storage backend."""

    def upsert(self, documents: Sequence[Document]) -> tuple[str, ...]: ...
