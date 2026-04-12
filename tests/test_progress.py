from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from docprep.progress import IngestProgressEvent, ProgressCallback


def test_ingest_progress_event_is_kw_only() -> None:
    assert all(field.kw_only for field in fields(IngestProgressEvent))


def test_ingest_progress_event_is_frozen() -> None:
    event = IngestProgressEvent(stage="run", event="started")

    with pytest.raises(FrozenInstanceError):
        setattr(event, "source_uri", "docs/example.md")


def test_ingest_progress_event_uses_slots() -> None:
    assert hasattr(IngestProgressEvent, "__slots__")


def test_ingest_progress_event_optional_fields_default_to_none() -> None:
    event = IngestProgressEvent(stage="run", event="started")

    assert event.source_uri is None
    assert event.current is None
    assert event.total is None
    assert event.elapsed_ms is None
    assert event.sections_count is None
    assert event.chunks_count is None
    assert event.sink_name is None
    assert event.error_type is None


def test_ingest_progress_event_accepts_all_fields() -> None:
    event = IngestProgressEvent(
        stage="persist",
        event="failed",
        source_uri="docs/example.md",
        current=2,
        total=3,
        elapsed_ms=12.5,
        sections_count=4,
        chunks_count=5,
        sink_name="SQLAlchemySink",
        error_type="RuntimeError",
    )

    assert event == IngestProgressEvent(
        stage="persist",
        event="failed",
        source_uri="docs/example.md",
        current=2,
        total=3,
        elapsed_ms=12.5,
        sections_count=4,
        chunks_count=5,
        sink_name="SQLAlchemySink",
        error_type="RuntimeError",
    )


def test_plain_function_can_be_used_as_progress_callback() -> None:
    events: list[IngestProgressEvent] = []

    def callback(event: IngestProgressEvent) -> None:
        events.append(event)

    progress_callback: ProgressCallback = callback
    progress_callback(IngestProgressEvent(stage="run", event="completed"))

    assert events == [IngestProgressEvent(stage="run", event="completed")]
