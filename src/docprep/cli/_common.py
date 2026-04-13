from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docprep.sinks.sqlalchemy import SQLAlchemySink


def _add_config_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default=None, metavar="PATH", help="Path to docprep.toml")


def _add_json_group(p: argparse.ArgumentParser) -> None:
    group = p.add_mutually_exclusive_group()
    group.add_argument("--json", dest="as_json", action="store_true", default=None)
    group.add_argument("--no-json", dest="as_json", action="store_false")


def _load_cli_config(args: argparse.Namespace) -> None:
    from docprep.config import DocPrepConfig, load_discovered_config

    config = load_discovered_config(explicit_path=getattr(args, "config", None))
    args.docprep_config = config or DocPrepConfig()


def _resolve_json(args: argparse.Namespace) -> bool:
    as_json: bool | None = args.as_json
    if as_json is not None:
        return as_json
    return args.docprep_config.json or False


def _resolve_source(args: argparse.Namespace) -> str:
    source = getattr(args, "source", None)
    if source is not None:
        return str(source)

    resolved = args.docprep_config.resolved_source()
    if resolved is not None:
        return str(resolved)

    from docprep.exceptions import ConfigError

    raise ConfigError("No source specified: provide source argument or set 'source' in config")


def _get_sink(args: argparse.Namespace) -> SQLAlchemySink:
    from sqlalchemy import create_engine

    from docprep.exceptions import ConfigError
    from docprep.sinks.sqlalchemy import SQLAlchemySink

    db_url = getattr(args, "db", None)
    config = args.docprep_config
    if db_url is None and config.sink is not None:
        db_url = config.sink.database_url
    if db_url is None:
        raise ConfigError(
            "No database URL specified: provide --db argument or set 'sink.database_url' in config"
        )

    engine = create_engine(db_url)
    return SQLAlchemySink(engine=engine, create_tables=False)
