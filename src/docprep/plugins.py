"""Plugin discovery via entry points."""

from __future__ import annotations

import importlib.metadata
import logging
import warnings

logger = logging.getLogger(__name__)

LOADER_GROUP = "docprep.loaders"
PARSER_GROUP = "docprep.parsers"
CHUNKER_GROUP = "docprep.chunkers"
SINK_GROUP = "docprep.sinks"


def discover_entry_points(group: str) -> dict[str, object]:
    """Discover and load entry points for a given group.

    Returns a mapping of entry-point names to loaded objects.
    Import or load failures emit warnings and are skipped.
    """
    discovered: dict[str, object] = {}

    try:
        entry_points = importlib.metadata.entry_points(group=group)
    except Exception as exc:
        message = (
            f"Unable to discover plugins for entry-point group '{group}'. "
            f"Built-in components remain available. Error: {exc}"
        )
        logger.warning(message)
        warnings.warn(message, RuntimeWarning, stacklevel=2)
        return discovered

    for entry_point in entry_points:
        try:
            discovered[entry_point.name] = entry_point.load()
        except Exception as exc:
            message = (
                f"Failed to load plugin '{entry_point.name}' from '{group}' "
                f"({entry_point.value}). Check that the package and its dependencies "
                f"are installed correctly. Error: {exc}"
            )
            logger.warning(message)
            warnings.warn(message, RuntimeWarning, stacklevel=2)

    return discovered
