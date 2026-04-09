"""Command-line interface for docprep."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

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

    _add_ingest_parser(subparsers)
    _add_preview_parser(subparsers)
    _add_stats_parser(subparsers)

    args = parser.parse_args(argv)

    try:
        handler = _COMMANDS[args.command]
        return handler(args)
    except DocPrepError as exc:
        print(f"docprep: error: {exc}", file=sys.stderr)
        return 1


def _add_ingest_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("ingest", help="Ingest documents into a database")
    p.add_argument("source", help="File or directory path to ingest")
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    p.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")


def _add_preview_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("preview", help="Preview document structure and chunks")
    p.add_argument("source", help="File or directory path to preview")
    p.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")


def _add_stats_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("stats", help="Show database statistics")
    p.add_argument("db", help="SQLAlchemy database URL")
    p.add_argument("--json", dest="as_json", action="store_true", help="Output as JSON")


def _cmd_ingest(args: argparse.Namespace) -> int:
    from docprep.chunkers.heading import HeadingChunker
    from docprep.chunkers.size import SizeChunker
    from docprep.cli.formatters import format_ingest_result
    from docprep.ingest import Ingestor

    sink = None
    if args.db:
        from sqlalchemy import create_engine

        from docprep.sinks.sqlalchemy import SQLAlchemySink

        engine = create_engine(args.db)
        sink = SQLAlchemySink(engine=engine)

    ingestor = Ingestor(chunkers=[HeadingChunker(), SizeChunker()], sink=sink)
    result = ingestor.run(args.source)
    print(format_ingest_result(result, as_json=args.as_json))
    return 0


def _cmd_preview(args: argparse.Namespace) -> int:
    from docprep.chunkers.heading import HeadingChunker
    from docprep.chunkers.size import SizeChunker
    from docprep.cli.formatters import format_preview
    from docprep.ingest import Ingestor

    ingestor = Ingestor(chunkers=[HeadingChunker(), SizeChunker()])
    result = ingestor.run(args.source)
    print(format_preview(result.documents, as_json=args.as_json))
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    from sqlalchemy import create_engine

    from docprep.cli.formatters import format_stats
    from docprep.sinks.sqlalchemy import SQLAlchemySink

    engine = create_engine(args.db)
    sink = SQLAlchemySink(engine=engine, create_tables=False)
    stats = sink.stats()
    stats_dict = {"documents": stats.documents, "sections": stats.sections, "chunks": stats.chunks}
    print(format_stats(stats_dict, as_json=args.as_json))
    return 0


_COMMANDS = {
    "ingest": _cmd_ingest,
    "preview": _cmd_preview,
    "stats": _cmd_stats,
}


def _get_version() -> str:
    from docprep import __version__

    return __version__
