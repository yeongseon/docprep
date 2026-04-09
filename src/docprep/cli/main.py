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


def _add_config_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default=None, metavar="PATH", help="Path to docprep.toml")


def _add_json_group(p: argparse.ArgumentParser) -> None:
    group = p.add_mutually_exclusive_group()
    group.add_argument("--json", dest="as_json", action="store_true", default=None)
    group.add_argument("--no-json", dest="as_json", action="store_false")


def _add_ingest_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("ingest", help="Ingest documents into a database")
    _add_config_arg(p)
    p.add_argument("source", nargs="?", default=None, help="File or directory path to ingest")
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    _add_json_group(p)


def _add_preview_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("preview", help="Preview document structure and chunks")
    _add_config_arg(p)
    p.add_argument("source", nargs="?", default=None, help="File or directory path to preview")
    _add_json_group(p)


def _add_stats_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("stats", help="Show database statistics")
    _add_config_arg(p)
    p.add_argument("db", nargs="?", default=None, help="SQLAlchemy database URL")
    _add_json_group(p)


def _load_cli_config(args: argparse.Namespace) -> None:
    from docprep.config import DocPrepConfig, load_discovered_config

    config = load_discovered_config(explicit_path=getattr(args, "config", None))
    args.docprep_config = config or DocPrepConfig()


def _resolve_json(args: argparse.Namespace) -> bool:
    # CLI flag > config > False
    as_json: bool | None = args.as_json
    if as_json is not None:
        return as_json
    return args.docprep_config.json or False


def _cmd_ingest(args: argparse.Namespace) -> int:
    from docprep.chunkers.heading import HeadingChunker
    from docprep.chunkers.size import SizeChunker
    from docprep.cli.formatters import format_ingest_result
    from docprep.config import DocPrepConfig
    from docprep.ingest import Ingestor
    from docprep.registry import build_chunkers, build_loader, build_parser

    _load_cli_config(args)
    config: DocPrepConfig = args.docprep_config
    as_json = _resolve_json(args)

    # Build components: explicit CLI args > config > defaults
    loader = build_loader(config.loader) if config.loader else None
    parser = build_parser(config.parser) if config.parser else None

    # Chunkers: config chunkers or CLI defaults (HeadingChunker + SizeChunker)
    if config.chunkers is not None:
        chunkers_list = list(build_chunkers(config.chunkers))
    else:
        chunkers_list = [HeadingChunker(), SizeChunker()]

    # Sink: CLI --db > config sink
    sink = None
    db_url = args.db
    if db_url is None and config.sink is not None:
        db_url = config.sink.database_url
    if db_url:
        from sqlalchemy import create_engine

        from docprep.sinks.sqlalchemy import SQLAlchemySink

        create_tables = config.sink.create_tables if config.sink else True
        engine = create_engine(db_url)
        sink = SQLAlchemySink(engine=engine, create_tables=create_tables)

    # Source: CLI positional > config source
    source = args.source
    if source is None:
        resolved = config.resolved_source()
        if resolved is None:
            from docprep.exceptions import ConfigError

            raise ConfigError(
                "No source specified: provide source argument or set 'source' in config"
            )
        source = resolved

    ingestor = Ingestor(loader=loader, parser=parser, chunkers=chunkers_list, sink=sink)
    result = ingestor.run(source)
    print(format_ingest_result(result, as_json=as_json))
    return 0


def _cmd_preview(args: argparse.Namespace) -> int:
    from docprep.chunkers.heading import HeadingChunker
    from docprep.chunkers.size import SizeChunker
    from docprep.cli.formatters import format_preview
    from docprep.config import DocPrepConfig
    from docprep.ingest import Ingestor
    from docprep.registry import build_chunkers, build_loader, build_parser

    _load_cli_config(args)
    config: DocPrepConfig = args.docprep_config
    as_json = _resolve_json(args)

    loader = build_loader(config.loader) if config.loader else None
    parser = build_parser(config.parser) if config.parser else None

    if config.chunkers is not None:
        chunkers_list = list(build_chunkers(config.chunkers))
    else:
        chunkers_list = [HeadingChunker(), SizeChunker()]

    source = args.source
    if source is None:
        resolved = config.resolved_source()
        if resolved is None:
            from docprep.exceptions import ConfigError

            raise ConfigError(
                "No source specified: provide source argument or set 'source' in config"
            )
        source = resolved

    ingestor = Ingestor(loader=loader, parser=parser, chunkers=chunkers_list)
    result = ingestor.run(source)
    print(format_preview(result.documents, as_json=as_json))
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    from sqlalchemy import create_engine

    from docprep.cli.formatters import format_stats
    from docprep.config import DocPrepConfig
    from docprep.sinks.sqlalchemy import SQLAlchemySink

    _load_cli_config(args)
    config: DocPrepConfig = args.docprep_config
    as_json = _resolve_json(args)

    db_url = args.db
    if db_url is None and config.sink is not None:
        db_url = config.sink.database_url
    if db_url is None:
        from docprep.exceptions import ConfigError

        raise ConfigError(
            "No database URL specified: provide db argument or set 'sink.database_url' in config"
        )

    engine = create_engine(db_url)
    sink = SQLAlchemySink(engine=engine, create_tables=False)
    stats = sink.stats()
    stats_dict = {"documents": stats.documents, "sections": stats.sections, "chunks": stats.chunks}
    print(format_stats(stats_dict, as_json=as_json))
    return 0


_COMMANDS = {
    "ingest": _cmd_ingest,
    "preview": _cmd_preview,
    "stats": _cmd_stats,
}


def _get_version() -> str:
    from docprep import __version__

    return __version__
