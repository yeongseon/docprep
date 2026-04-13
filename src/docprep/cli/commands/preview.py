from __future__ import annotations

import argparse

from docprep.cli._common import _add_config_arg, _add_json_group, _load_cli_config, _resolve_json


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = subparsers.add_parser("preview", help="Preview document structure and chunks")
    _add_config_arg(p)
    p.add_argument("source", nargs="?", default=None, help="File or directory path to preview")
    _add_json_group(p)


def handle(args: argparse.Namespace) -> int:
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
