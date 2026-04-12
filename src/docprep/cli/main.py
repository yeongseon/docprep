"""Command-line interface for docprep."""

from __future__ import annotations

import argparse
import json
import sys
from typing import TYPE_CHECKING, Sequence, TextIO

from docprep.exceptions import DocPrepError

if TYPE_CHECKING:
    from docprep.sinks.sqlalchemy import SQLAlchemySink


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
    _add_diff_parser(subparsers)
    _add_export_parser(subparsers)
    _add_inspect_parser(subparsers)
    _add_prune_parser(subparsers)
    _add_delete_parser(subparsers)

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


def _add_diff_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("diff", help="Show document changes against persisted database state")
    _add_config_arg(p)
    p.add_argument("source", nargs="?", default=None, help="File or directory path to diff")
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    _add_json_group(p)


def _add_export_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
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
        "--db", default=None, help="SQLAlchemy database URL (required for --changed-only)"
    )
    _add_json_group(p)


def _add_inspect_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("inspect", help="Inspect a document, section, or chunk by URI or ID")
    _add_config_arg(p)
    p.add_argument("query", help="source URI, document UUID, section UUID, or chunk UUID")
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    _add_json_group(p)


def _add_prune_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("prune", help="Remove stale documents no longer present in source")
    _add_config_arg(p)
    p.add_argument(
        "source", nargs="?", default=None, help="File or directory path to prune against"
    )
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    p.add_argument("--dry-run", action="store_true", help="Preview what would be deleted")
    _add_json_group(p)


def _add_delete_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("delete", help="Delete a document by source URI")
    _add_config_arg(p)
    p.add_argument("uri", help="Document source URI (e.g. file:guide.md)")
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    p.add_argument("--dry-run", action="store_true", help="Preview what would be deleted")
    _add_json_group(p)


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


def _cmd_ingest(args: argparse.Namespace) -> int:
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


def _cmd_preview(args: argparse.Namespace) -> int:
    from docprep.cli.formatters import format_preview
    from docprep.config import DocPrepConfig
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


def _cmd_diff(args: argparse.Namespace) -> int:
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


def _cmd_export(args: argparse.Namespace) -> int:
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
                iter_vector_records_v1(result.documents, text_prepend=text_prepend),
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


def _cmd_inspect(args: argparse.Namespace) -> int:
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


def _cmd_prune(args: argparse.Namespace) -> int:
    from docprep.cli.formatters import format_delete_result
    from docprep.config import DocPrepConfig
    from docprep.loaders.markdown import MarkdownLoader
    from docprep.registry import build_loader
    from docprep.scope import derive_scope, uri_in_scope

    _load_cli_config(args)
    config: DocPrepConfig = args.docprep_config
    as_json = _resolve_json(args)
    source = _resolve_source(args)
    sink = _get_sink(args)

    loader = build_loader(config.loader) if config.loader else MarkdownLoader()
    loaded_sources = list(loader.load(source))
    loaded_uris = {loaded_source.source_uri for loaded_source in loaded_sources}

    scope = derive_scope(source)
    stored_uris: set[str] = set()
    offset = 0
    page_size = 200
    while True:
        page = sink.list_documents(offset=offset, limit=page_size)
        for item in page.items:
            source_uri = getattr(item, "source_uri", "")
            if uri_in_scope(source_uri, scope):
                stored_uris.add(source_uri)
        if not page.has_more:
            break
        offset += page_size

    stale_uris = sorted(stored_uris - loaded_uris)
    result = sink.delete_by_uris(stale_uris, dry_run=args.dry_run)

    if as_json:
        print(format_delete_result(result, as_json=True))
        return 0

    if result.deleted_document_count == 0:
        prefix = "[DRY RUN] Would prune" if args.dry_run else "Pruned"
        print(f"{prefix} 0 document(s).")
        return 0

    prefix = "[DRY RUN] Would prune" if args.dry_run else "Pruned"
    lines = [f"{prefix} {result.deleted_document_count} document(s):"]
    for source_uri in result.deleted_source_uris:
        lines.append(f"  {source_uri}")
    print("\n".join(lines))
    return 0


def _cmd_delete(args: argparse.Namespace) -> int:
    from docprep.cli.formatters import format_delete_result

    _load_cli_config(args)
    as_json = _resolve_json(args)
    sink = _get_sink(args)
    result = sink.delete_by_uri(args.uri, dry_run=args.dry_run)
    print(format_delete_result(result, as_json=as_json))
    return 0


_COMMANDS = {
    "ingest": _cmd_ingest,
    "preview": _cmd_preview,
    "stats": _cmd_stats,
    "diff": _cmd_diff,
    "export": _cmd_export,
    "inspect": _cmd_inspect,
    "prune": _cmd_prune,
    "delete": _cmd_delete,
}


def _get_version() -> str:
    from docprep import __version__

    return __version__
