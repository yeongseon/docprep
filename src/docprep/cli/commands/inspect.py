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
    p = subparsers.add_parser("inspect", help="Inspect a document, section, or chunk by URI or ID")
    _add_config_arg(p)
    p.add_argument("query", help="source URI, document UUID, section UUID, or chunk UUID")
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    _add_json_group(p)


def handle(args: argparse.Namespace) -> int:
    import uuid

    from docprep.cli.formatters import (
        format_inspect_chunk,
        format_inspect_document,
        format_inspect_section,
    )
    from docprep.exceptions import DocPrepError

    _load_cli_config(args)
    as_json = _resolve_json(args)
    sink = _get_sink(args)

    query = args.query
    if query.startswith("file:"):
        document = sink.get_document(query)
        if document is None:
            raise DocPrepError(f"No record found for query: {query}")
        print(format_inspect_document(document, as_json=as_json))
        return 0

    try:
        query_uuid = uuid.UUID(query)
    except ValueError:
        document = sink.get_document(query)
        if document is None:
            raise DocPrepError(f"No record found for query: {query}")
        print(format_inspect_document(document, as_json=as_json))
        return 0

    document = sink.get_document_by_id(query_uuid)
    if document is not None:
        print(format_inspect_document(document, as_json=as_json))
        return 0

    section = sink.get_section(query_uuid)
    if section is not None:
        print(format_inspect_section(section, as_json=as_json))
        return 0

    chunk = sink.get_chunk(query_uuid)
    if chunk is not None:
        print(format_inspect_chunk(chunk, as_json=as_json))
        return 0

    raise DocPrepError(f"No record found for query: {query}")
