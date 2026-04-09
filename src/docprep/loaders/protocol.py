"""Loader protocol — loads raw content from sources."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from docprep.loaders.types import LoadedSource


@runtime_checkable
class Loader(Protocol):
    """Loads raw content from one or more sources."""

    def load(self, source: str | Path) -> Iterable[LoadedSource]: ...
