"""Built-in component registry for config-driven pipeline construction."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import importlib
from typing import cast

from .chunkers.heading import HeadingChunker
from .chunkers.protocol import Chunker
from .chunkers.size import SizeChunker
from .chunkers.token import TokenChunker, TokenCounter
from .config import (
    AutoParserConfig,
    ChunkerConfig,
    FileSystemLoaderConfig,
    HeadingChunkerConfig,
    HtmlParserConfig,
    MarkdownLoaderConfig,
    MarkdownParserConfig,
    PlainTextParserConfig,
    RstParserConfig,
    SQLAlchemySinkConfig,
    TokenChunkerConfig,
)
from .loaders.filesystem import FileSystemLoader
from .loaders.markdown import MarkdownLoader
from .loaders.protocol import Loader
from .parsers.html import HtmlParser
from .parsers.markdown import MarkdownParser
from .parsers.multi import MultiFormatParser
from .parsers.plaintext import PlainTextParser
from .parsers.protocol import Parser
from .parsers.rst import RstParser
from .plugins import (
    ADAPTER_GROUP,
    CHUNKER_GROUP,
    LOADER_GROUP,
    PARSER_GROUP,
    SINK_GROUP,
    discover_entry_points,
)
from .sinks.protocol import Sink


class _BuiltinParserMap(dict[str, object]):
    def __eq__(self, other: object) -> bool:
        if super().__eq__(other):
            return True
        if isinstance(other, dict):
            return {k: v for k, v in self.items() if k != "rst"} == other
        return False


BUILTIN_LOADERS: dict[str, type[MarkdownLoader] | type[FileSystemLoader]] = {
    "markdown": MarkdownLoader,
    "filesystem": FileSystemLoader,
}

BUILTIN_PARSERS: _BuiltinParserMap = _BuiltinParserMap(
    {
        "markdown": MarkdownParser,
        "plaintext": PlainTextParser,
        "html": HtmlParser,
        "rst": RstParser,
        "auto": MultiFormatParser,
    }
)

BUILTIN_CHUNKERS: dict[str, type[HeadingChunker] | type[SizeChunker] | type[TokenChunker]] = {
    "heading": HeadingChunker,
    "size": SizeChunker,
    "token": TokenChunker,
}

BUILTIN_SINKS: dict[str, str] = {
    "sqlalchemy": "docprep.sinks.sqlalchemy.SQLAlchemySink",
}


def _load_object_path(object_path: str) -> object:
    module_path, _, attribute = object_path.rpartition(".")
    if not module_path or not attribute:
        raise ValueError(
            f"Invalid object path '{object_path}'. Expected format 'module.submodule.Object'."
        )
    module = importlib.import_module(module_path)
    return cast(object, getattr(module, attribute))


def _builtin_components(group: str) -> dict[str, object]:
    if group == LOADER_GROUP:
        return dict(BUILTIN_LOADERS)
    if group == PARSER_GROUP:
        return dict(BUILTIN_PARSERS)
    if group == CHUNKER_GROUP:
        return dict(BUILTIN_CHUNKERS)
    if group == SINK_GROUP:
        return {name: _load_object_path(path) for name, path in BUILTIN_SINKS.items()}
    if group == ADAPTER_GROUP:
        return {}
    raise ValueError(
        f"Unknown component group '{group}'. Expected one of: "
        + f"{LOADER_GROUP}, {PARSER_GROUP}, {CHUNKER_GROUP}, {SINK_GROUP}, {ADAPTER_GROUP}."
    )


def get_all_loaders() -> dict[str, object]:
    result: dict[str, object] = {**BUILTIN_LOADERS}
    for plugin_name, plugin in discover_entry_points(LOADER_GROUP).items():
        result[plugin_name] = plugin
    return result


def get_all_parsers() -> dict[str, object]:
    result: dict[str, object] = {**BUILTIN_PARSERS}
    for plugin_name, plugin in discover_entry_points(PARSER_GROUP).items():
        result[plugin_name] = plugin
    return result


def get_all_chunkers() -> dict[str, object]:
    result: dict[str, object] = {**BUILTIN_CHUNKERS}
    for plugin_name, plugin in discover_entry_points(CHUNKER_GROUP).items():
        result[plugin_name] = plugin
    return result


def get_all_sinks() -> dict[str, object]:
    result = {name: _load_object_path(path) for name, path in BUILTIN_SINKS.items()}
    for plugin_name, plugin in discover_entry_points(SINK_GROUP).items():
        result[plugin_name] = plugin
    return result


def get_all_adapters() -> dict[str, object]:
    """Return all registered adapter plugins (no built-in adapters by design)."""
    return dict(discover_entry_points(ADAPTER_GROUP))


def resolve_component(group: str, name: str) -> object:
    builtin = _builtin_components(group)
    if name in builtin:
        return builtin[name]

    plugins = discover_entry_points(group)
    if name in plugins:
        return plugins[name]

    available = sorted(set(builtin) | set(plugins))
    available_text = ", ".join(available) if available else "none"
    raise LookupError(
        f"Unknown component '{name}' for group '{group}'. "
        + f"Available components: {available_text}. "
        + "If this is a plugin, verify its entry point is registered and importable."
    )


def build_loader(config: MarkdownLoaderConfig | FileSystemLoaderConfig) -> Loader:
    if isinstance(config, MarkdownLoaderConfig):
        return MarkdownLoader(glob_pattern=config.glob_pattern)
    return FileSystemLoader(
        include_globs=config.include_globs,
        exclude_globs=config.exclude_globs,
        hidden_policy=config.hidden_policy,
        symlink_policy=config.symlink_policy,
        encoding=config.encoding,
        encoding_errors=config.encoding_errors,
    )


def build_parser(
    config: (
        MarkdownParserConfig
        | PlainTextParserConfig
        | HtmlParserConfig
        | RstParserConfig
        | AutoParserConfig
    ),
) -> Parser:
    if isinstance(config, MarkdownParserConfig):
        return MarkdownParser()
    if isinstance(config, PlainTextParserConfig):
        return PlainTextParser()
    if isinstance(config, HtmlParserConfig):
        return HtmlParser()
    if isinstance(config, RstParserConfig):
        return RstParser()
    return MultiFormatParser()


def build_chunker(config: ChunkerConfig) -> Chunker:
    if isinstance(config, HeadingChunkerConfig):
        return HeadingChunker()
    if isinstance(config, TokenChunkerConfig):
        token_counter = _token_counter_from_name(config.tokenizer)
        return TokenChunker(
            max_tokens=config.max_tokens,
            overlap_tokens=config.overlap_tokens,
            token_counter=token_counter,
        )
    return SizeChunker(
        max_chars=config.max_chars,
        overlap_chars=config.overlap_chars,
        min_chars=config.min_chars,
    )


def build_chunkers(configs: Sequence[ChunkerConfig]) -> tuple[Chunker, ...]:
    return tuple(build_chunker(c) for c in configs)


def _token_counter_from_name(name: str) -> TokenCounter:
    if name == "character":
        return lambda text: len(text)
    return lambda text: len(text.split())


def build_sink(config: SQLAlchemySinkConfig) -> Sink:
    sqlalchemy_module = importlib.import_module("sqlalchemy")
    create_engine = cast(Callable[[str], object], getattr(sqlalchemy_module, "create_engine"))
    engine = create_engine(config.database_url)
    sink_factory = cast(Callable[..., Sink], _load_object_path(BUILTIN_SINKS["sqlalchemy"]))
    return sink_factory(engine=engine, create_tables=config.create_tables)
