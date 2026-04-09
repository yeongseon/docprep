"""Data types for the loader subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, kw_only=True, slots=True)
class LoadedSource:
    """Raw content loaded from a single source file."""

    source_path: str
    source_uri: str
    raw_text: str
    checksum: str
    media_type: str = "text/markdown"
    source_metadata: dict[str, Any] = field(default_factory=dict)
