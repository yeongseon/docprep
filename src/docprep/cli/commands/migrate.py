from __future__ import annotations

import argparse

from docprep.cli._common import _add_config_arg, _get_sink, _load_cli_config


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser(
        "migrate", help="Run database migrations to match current schema version"
    )
    _add_config_arg(p)
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")


def handle(args: argparse.Namespace) -> int:
    _load_cli_config(args)
    sink = _get_sink(args)
    sink.migrate()
    print("Database schema is up to date.")
    return 0
