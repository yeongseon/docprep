"""Progress callback protocol and event dataclass for the ingest pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from docprep.models.domain import PipelineStage


@dataclass(frozen=True, kw_only=True, slots=True)
class IngestProgressEvent:
    """A progress event emitted during an ingest pipeline run."""

    stage: PipelineStage
    event: Literal["started", "completed", "failed", "skipped", "updated"]
    source_uri: str | None = None
    current: int | None = None
    total: int | None = None
    elapsed_ms: float | None = None
    sections_count: int | None = None
    chunks_count: int | None = None
    sink_name: str | None = None
    error_type: str | None = None


class ProgressCallback(Protocol):
    """Callback protocol for receiving ingest progress events."""

    def __call__(self, event: IngestProgressEvent, /) -> None: ...
