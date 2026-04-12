"""Sink protocol — persists documents to storage."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable
import uuid

from docprep.models.domain import Document, SinkUpsertResult


@runtime_checkable
class Sink(Protocol):
    """Persists documents to a storage backend."""

    def upsert(
        self,
        documents: Sequence[Document],
        *,
        run_id: uuid.UUID | None = None,
    ) -> SinkUpsertResult: ...
