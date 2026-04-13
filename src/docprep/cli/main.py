"""Command-line interface for docprep."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from docprep.cli.commands import (
    delete,
    diff,
    export,
    ingest,
    inspect,
    migrate,
    preview,
    prune,
    stats,
)
from docprep.exceptions import DocPrepError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docprep",
        description="Prepare documents into structured, vector-ready data",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )

    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    ingest.register(subparsers)
    preview.register(subparsers)
    stats.register(subparsers)
    diff.register(subparsers)
    export.register(subparsers)
    inspect.register(subparsers)
    prune.register(subparsers)
    delete.register(subparsers)
    migrate.register(subparsers)

    args = parser.parse_args(argv)

    try:
        handler = _COMMANDS[args.command]
        return handler(args)
    except DocPrepError as exc:
        print(f"docprep: error: {exc}", file=sys.stderr)
        return 1


_COMMANDS = {
    "ingest": ingest.handle,
    "preview": preview.handle,
    "stats": stats.handle,
    "diff": diff.handle,
    "export": export.handle,
    "inspect": inspect.handle,
    "prune": prune.handle,
    "delete": delete.handle,
    "migrate": migrate.handle,
}


def _get_version() -> str:
    from docprep import __version__

    return __version__
