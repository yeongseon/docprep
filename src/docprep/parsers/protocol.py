"""Parser protocol — converts loaded sources into Documents."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from docprep.loaders.types import LoadedSource
from docprep.models.domain import Document


@runtime_checkable
class Parser(Protocol):
    """Parses a loaded source into a Document (without sections or chunks)."""

    def parse(self, loaded_source: LoadedSource) -> Document: ...
