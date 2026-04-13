from __future__ import annotations

import argparse

from docprep.cli._common import _add_config_arg, _add_json_group, _load_cli_config, _resolve_json


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("stats", help="Show database statistics")
    _add_config_arg(p)
    p.add_argument("db", nargs="?", default=None, help="SQLAlchemy database URL")
    _add_json_group(p)


def handle(args: argparse.Namespace) -> int:
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
    stats_result = sink.stats()
    stats_dict = {
        "documents": stats_result.documents,
        "sections": stats_result.sections,
        "chunks": stats_result.chunks,
    }
    print(format_stats(stats_dict, as_json=as_json))
    return 0
