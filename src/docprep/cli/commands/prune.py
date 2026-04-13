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
    p = subparsers.add_parser("prune", help="Remove stale documents no longer present in source")
    _add_config_arg(p)
    p.add_argument(
        "source",
        nargs="?",
        default=None,
        help="File or directory path to prune against",
    )
    p.add_argument("--db", default=None, help="SQLAlchemy database URL (e.g. sqlite:///docs.db)")
    p.add_argument("--dry-run", action="store_true", help="Preview what would be deleted")
    _add_json_group(p)


def handle(args: argparse.Namespace) -> int:
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
