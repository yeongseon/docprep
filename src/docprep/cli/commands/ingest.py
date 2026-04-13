from __future__ import annotations

import argparse

from docprep.cli._common import _add_config_arg, _add_json_group, _load_cli_config, _resolve_json


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("ingest", help="Ingest documents into a database")
    _add_config_arg(p)
    p.add_argument("source", nargs="?", default=None, help="File or directory path to ingest")
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    p.add_argument(
        "--log-format",
        choices=["human", "json"],
        default="human",
        dest="log_format",
        help="Log output format (default: human)",
    )
    p.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        dest="log_level",
        help="Log verbosity level (default: info)",
    )
    p.add_argument(
        "--error-mode",
        choices=["fail_fast", "continue_on_error"],
        default="continue_on_error",
        dest="error_mode",
        help="Error handling mode (default: continue_on_error)",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help="Resume from last checkpoint, skipping unchanged sources",
    )
    p.add_argument(
        "--checkpoint-path",
        default=None,
        metavar="PATH",
        dest="checkpoint_path",
        help="Path to checkpoint file (default: .docprep-checkpoint.json)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="Number of parallel workers for parse/chunk (default: 1)",
    )
    _add_json_group(p)


def handle(args: argparse.Namespace) -> int:
    from docprep.cli.formatters import format_ingest_result
    from docprep.cli.logging import setup_cli_logger
    from docprep.config import DocPrepConfig
    from docprep.ingest import DEFAULT_CHUNKERS, Ingestor
    from docprep.models.domain import ErrorMode
    from docprep.registry import build_chunkers, build_loader, build_parser

    _load_cli_config(args)
    config: DocPrepConfig = args.docprep_config
    as_json = _resolve_json(args)

    logger = setup_cli_logger(
        log_format=args.log_format,
        log_level=args.log_level,
    )

    loader = build_loader(config.loader) if config.loader else None
    parser = build_parser(config.parser) if config.parser else None

    if config.chunkers is not None:
        chunkers_list = list(build_chunkers(config.chunkers))
    else:
        chunkers_list = list(DEFAULT_CHUNKERS)

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

    source = args.source
    if source is None:
        resolved = config.resolved_source()
        if resolved is None:
            from docprep.exceptions import ConfigError

            raise ConfigError(
                "No source specified: provide source argument or set 'source' in config"
            )
        source = resolved

    ingestor = Ingestor(
        loader=loader,
        parser=parser,
        chunkers=chunkers_list,
        sink=sink,
        logger=logger,
        error_mode=ErrorMode(args.error_mode),
    )
    result = ingestor.run(
        source,
        workers=args.workers,
        resume=args.resume,
        checkpoint_path=args.checkpoint_path,
    )
    print(format_ingest_result(result, as_json=as_json))
    if result.failed_count > 0 and result.processed_count > 0:
        return 3
    if result.errors and result.processed_count == 0:
        return 1
    return 0
