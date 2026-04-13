from __future__ import annotations

import argparse

from docprep.cli._common import (
    _add_config_arg,
    _add_json_group,
    _get_sink,
    _load_cli_config,
    _resolve_json,
    _resolve_source,
)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("diff", help="Show document changes against persisted database state")
    _add_config_arg(p)
    p.add_argument("source", nargs="?", default=None, help="File or directory path to diff")
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    _add_json_group(p)


def handle(args: argparse.Namespace) -> int:
    from docprep.cli.formatters import format_diff
    from docprep.config import DocPrepConfig
    from docprep.diff import compute_diff_from_documents
    from docprep.ingest import DEFAULT_CHUNKERS, Ingestor
    from docprep.registry import build_chunkers, build_loader, build_parser

    _load_cli_config(args)
    config: DocPrepConfig = args.docprep_config
    as_json = _resolve_json(args)

    loader = build_loader(config.loader) if config.loader else None
    parser = build_parser(config.parser) if config.parser else None

    if config.chunkers is not None:
        chunkers_list = list(build_chunkers(config.chunkers))
    else:
        chunkers_list = list(DEFAULT_CHUNKERS)

    source = _resolve_source(args)
    ingestor = Ingestor(loader=loader, parser=parser, chunkers=chunkers_list)
    result = ingestor.run(source)

    sink = _get_sink(args)
    diffs = []
    for document in result.documents:
        previous_document = sink.get_document(document.source_uri)
        diffs.append(compute_diff_from_documents(previous_document, document))

    print(format_diff(diffs, as_json=as_json))
    return 0
