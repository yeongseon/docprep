"""CLI logging setup — human-readable and JSON formatters for stderr output."""

from __future__ import annotations

import json
import logging
import sys
from typing import Literal

_SENTINEL_ATTR = "_docprep_cli_handler"

_EXTRA_KEYS = (
    "stage", "event", "source_uri", "error_type", "sink_name",
    "count", "sections_count", "chunks_count",
    "updated_count", "skipped_count", "processed_count", "failed_count",
    "elapsed_ms", "current", "total", "deleted_count",
)


class HumanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname.lower()
        msg = record.getMessage()

        stage = getattr(record, "stage", None)
        if stage is not None:
            return f"[{level}] [{stage}] {msg}"

        return f"[{level}] {msg}"


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
            "logger": record.name,
        }

        for key in _EXTRA_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value

        return json.dumps(entry, default=str)


def setup_cli_logger(
    *,
    log_format: Literal["human", "json"] = "human",
    log_level: str = "info",
) -> logging.Logger:
    logger = logging.getLogger("docprep.ingest")
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.propagate = False

    for h in list(logger.handlers):
        if getattr(h, _SENTINEL_ATTR, False):
            logger.removeHandler(h)
            h.close()

    handler = logging.StreamHandler(stream=sys.stderr)
    setattr(handler, _SENTINEL_ATTR, True)

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(HumanFormatter())

    logger.addHandler(handler)
    return logger
