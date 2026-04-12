"""Adapter protocol for external document converters."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..models.domain import Document


@runtime_checkable
class Adapter(Protocol):
    """Converts external tool output into docprep Documents."""

    def convert(self, source: str | Path) -> Iterable[Document]: ...

    @property
    def supported_extensions(self) -> frozenset[str]: ...
