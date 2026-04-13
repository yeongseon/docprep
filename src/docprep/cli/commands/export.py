from __future__ import annotations

import argparse
import json
import sys
from typing import TextIO

from docprep.cli._common import (
    _add_config_arg,
    _add_json_group,
    _get_sink,
    _load_cli_config,
    _resolve_json,
    _resolve_source,
)


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("export", help="Export vector records as JSONL")
    _add_config_arg(p)
    p.add_argument("source", nargs="?", default=None, help="File or directory path")
    p.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="FILE",
        help="Output file (default: stdout)",
    )
    p.add_argument(
        "--format",
        choices=["v1"],
        default="v1",
        dest="export_format",
        help="Record format (default: v1)",
    )
    p.add_argument(
        "--changed-only",
        action="store_true",
        help="Export only added/modified records since last sync",
    )
    p.add_argument(
        "--db",
        default=None,
        help="SQLAlchemy database URL (required for --changed-only)",
    )
    _add_json_group(p)


def handle(args: argparse.Namespace) -> int:
    from docprep.cli.formatters import format_export_summary
    from docprep.config import DocPrepConfig
    from docprep.diff import compute_diff_from_documents
    from docprep.exceptions import ConfigError
    from docprep.export import build_export_delta, iter_vector_records_v1, write_jsonl
    from docprep.ingest import DEFAULT_CHUNKERS, Ingestor
    from docprep.models.domain import Document, TextPrependStrategy
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

    text_prepend_value = (
        config.export.text_prepend
        if config.export is not None
        else TextPrependStrategy.TITLE_AND_HEADING_PATH
    )
    text_prepend = (
        TextPrependStrategy(text_prepend_value)
        if isinstance(text_prepend_value, str)
        else text_prepend_value
    )
    include_annotations = config.export.include_annotations if config.export is not None else False

    records_written = 0
    deleted_written = 0

    output: TextIO
    if args.output is not None:
        output = open(args.output, "w", encoding="utf-8")
        should_close_output = True
    else:
        output = sys.stdout
        should_close_output = False

    try:
        if args.changed_only:
            if not getattr(args, "db", None) and (
                config.sink is None or not config.sink.database_url
            ):
                raise ConfigError("--changed-only requires --db or config sink.database_url")

            sink = _get_sink(args)
            current_docs = result.documents
            current_by_uri = {document.source_uri: document for document in current_docs}
            stored_uris: set[str] = set()
            offset = 0
            page_size = 200
            while True:
                page = sink.list_documents(offset=offset, limit=page_size)
                for item in page.items:
                    source_uri = getattr(item, "source_uri", "")
                    if source_uri:
                        stored_uris.add(source_uri)
                if not page.has_more:
                    break
                offset += page_size

            diffs = []
            for document in current_docs:
                previous_document = sink.get_document(document.source_uri)
                diffs.append(compute_diff_from_documents(previous_document, document))

            missing_uris = sorted(stored_uris - set(current_by_uri))
            for source_uri in missing_uris:
                previous_document = sink.get_document(source_uri)
                if previous_document is None:
                    continue
                empty_document = Document(
                    id=previous_document.id,
                    source_uri=previous_document.source_uri,
                    title=previous_document.title,
                    source_checksum="",
                    source_type=previous_document.source_type,
                    frontmatter=previous_document.frontmatter,
                    source_metadata=previous_document.source_metadata,
                    body_markdown="",
                    sections=(),
                    chunks=(),
                )
                diffs.append(compute_diff_from_documents(previous_document, empty_document))

            delta = build_export_delta(
                tuple(diffs),
                current_docs,
                text_prepend=text_prepend,
                include_annotations=include_annotations,
            )
            records_written = write_jsonl(iter(delta.added + delta.modified), output)
            for deleted_id in delta.deleted_ids:
                output.write(
                    json.dumps({"_deleted": True, "id": str(deleted_id)}, ensure_ascii=False)
                )
                output.write("\n")
                deleted_written += 1
        else:
            records_written = write_jsonl(
                iter_vector_records_v1(
                    result.documents,
                    text_prepend=text_prepend,
                    include_annotations=include_annotations,
                ),
                output,
            )
    finally:
        if should_close_output:
            output.close()

    print(
        format_export_summary(
            records_written=records_written,
            deleted_written=deleted_written,
            changed_only=args.changed_only,
            as_json=as_json,
        ),
        file=sys.stderr,
    )
    return 0
