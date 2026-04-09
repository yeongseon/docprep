"""Command-line interface for docprep."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the docprep CLI."""
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

    subparsers.add_parser("ingest", help="Ingest documents into a database")
    subparsers.add_parser("preview", help="Preview document structure and chunks")
    subparsers.add_parser("stats", help="Show database statistics")

    args = parser.parse_args(argv)

    print(f"docprep: command '{args.command}' not yet implemented", file=sys.stderr)
    return 1


def _get_version() -> str:
    from docprep import __version__

    return __version__
