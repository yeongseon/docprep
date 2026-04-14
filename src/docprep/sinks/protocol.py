"""Sink protocol — persists documents to storage."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, runtime_checkable
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

    if TYPE_CHECKING:

        def get_documents_by_uris(self, source_uris: Sequence[str]) -> dict[str, Document]: ...
