from __future__ import annotations

import argparse

from docprep.cli._common import (
    _add_config_arg,
    _add_json_group,
    _get_sink,
    _load_cli_config,
    _resolve_json,
)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("delete", help="Delete a document by source URI")
    _add_config_arg(p)
    p.add_argument("uri", help="Document source URI (e.g. file:guide.md)")
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    p.add_argument("--dry-run", action="store_true", help="Preview what would be deleted")
    _add_json_group(p)


def handle(args: argparse.Namespace) -> int:
    from docprep.cli.formatters import format_delete_result

    _load_cli_config(args)
    as_json = _resolve_json(args)
    sink = _get_sink(args)
    result = sink.delete_by_uri(args.uri, dry_run=args.dry_run)
    print(format_delete_result(result, as_json=as_json))
    return 0
