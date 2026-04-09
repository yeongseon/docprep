from __future__ import annotations

import json
import logging
from typing import cast

from docprep.cli.logging import HumanFormatter, JSONFormatter, setup_cli_logger


def _record(
    *, level: int = logging.INFO, message: str = "message", **extra: object,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name="docprep.ingest",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_human_formatter_formats_level_and_message() -> None:
    formatter = HumanFormatter()

    assert formatter.format(_record(level=logging.WARNING, message="hello")) == "[warning] hello"


def test_human_formatter_includes_stage_when_present() -> None:
    formatter = HumanFormatter()

    assert formatter.format(_record(message="loaded", stage="load")) == "[info] [load] loaded"


def test_json_formatter_produces_valid_ndjson_entry() -> None:
    formatter = JSONFormatter()
    payload = cast(dict[str, object], json.loads(formatter.format(_record(message="loaded"))))

    assert payload["level"] == "info"
    assert payload["message"] == "loaded"
    assert payload["logger"] == "docprep.ingest"
    assert isinstance(payload["timestamp"], str)


def test_json_formatter_includes_extra_fields() -> None:
    formatter = JSONFormatter()
    payload = cast(
        dict[str, object],
        json.loads(
            formatter.format(
                _record(
                    level=logging.ERROR,
                    message="failed",
                    stage="parse",
                    event="failed",
                    source_uri="docs/example.md",
                    error_type="RuntimeError",
                    sink_name="SQLAlchemySink",
                    count=2,
                    sections_count=3,
                    chunks_count=4,
                    updated_count=5,
                    skipped_count=6,
                    processed_count=7,
                    failed_count=8,
                )
            )
        ),
    )

    assert payload == {
        "level": "error",
        "message": "failed",
        "timestamp": payload["timestamp"],
        "logger": "docprep.ingest",
        "stage": "parse",
        "event": "failed",
        "source_uri": "docs/example.md",
        "error_type": "RuntimeError",
        "sink_name": "SQLAlchemySink",
        "count": 2,
        "sections_count": 3,
        "chunks_count": 4,
        "updated_count": 5,
        "skipped_count": 6,
        "processed_count": 7,
        "failed_count": 8,
    }


def test_setup_cli_logger_returns_logger_with_correct_level_and_handler() -> None:
    logger = logging.getLogger("docprep.ingest")
    original_handlers = list(logger.handlers)
    original_level = logger.level
    logger.handlers.clear()

    try:
        configured = setup_cli_logger(log_level="debug")

        assert configured is logger
        assert configured.level == logging.DEBUG
        assert len(configured.handlers) == 1
        assert isinstance(configured.handlers[0], logging.StreamHandler)
    finally:
        logger.handlers[:] = original_handlers
        logger.setLevel(original_level)


def test_setup_cli_logger_with_json_format_uses_json_formatter() -> None:
    logger = logging.getLogger("docprep.ingest")
    original_handlers = list(logger.handlers)
    logger.handlers.clear()

    try:
        configured = setup_cli_logger(log_format="json")

        assert isinstance(configured.handlers[-1].formatter, JSONFormatter)
    finally:
        logger.handlers[:] = original_handlers


def test_setup_cli_logger_with_human_format_uses_human_formatter() -> None:
    logger = logging.getLogger("docprep.ingest")
    original_handlers = list(logger.handlers)
    logger.handlers.clear()

    try:
        configured = setup_cli_logger(log_format="human")

        assert isinstance(configured.handlers[-1].formatter, HumanFormatter)
    finally:
        logger.handlers[:] = original_handlers


def test_json_formatter_includes_elapsed_ms_and_numeric_fields() -> None:
    formatter = JSONFormatter()
    payload = cast(
        dict[str, object],
        json.loads(
            formatter.format(
                _record(
                    message="done",
                    elapsed_ms=42.5,
                    current=3,
                    total=10,
                    deleted_count=0,
                )
            )
        ),
    )

    assert payload["elapsed_ms"] == 42.5
    assert payload["current"] == 3
    assert payload["total"] == 10


def test_setup_cli_logger_is_idempotent() -> None:
    logger = logging.getLogger("docprep.ingest")
    original_handlers = list(logger.handlers)
    logger.handlers.clear()

    try:
        _ = setup_cli_logger(log_format="human")
        _ = setup_cli_logger(log_format="json")
        configured = setup_cli_logger(log_format="human", log_level="debug")

        cli_handlers = [
            h for h in configured.handlers
            if getattr(h, "_docprep_cli_handler", False)
        ]
        assert len(cli_handlers) == 1
        assert isinstance(cli_handlers[0].formatter, HumanFormatter)
        assert configured.level == logging.DEBUG
        assert configured.propagate is False
    finally:
        logger.handlers[:] = original_handlers
