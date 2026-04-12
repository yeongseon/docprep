"""Configuration loading, discovery, and validation for docprep."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore[no-redef]
from typing import Any, Literal

from .exceptions import ConfigError

_CONFIG_FILENAME = "docprep.toml"

_ROOT_KEYS = frozenset({"source", "json", "loader", "parser", "chunkers", "sink", "export"})
_LOADER_KEYS = frozenset(
    {
        "type",
        "glob_pattern",
        "include_globs",
        "exclude_globs",
        "hidden_policy",
        "symlink_policy",
        "encoding",
        "encoding_errors",
    }
)
_PARSER_KEYS = frozenset({"type"})
_HEADING_CHUNKER_KEYS = frozenset({"type"})
_SIZE_CHUNKER_KEYS = frozenset({"type", "max_chars", "overlap_chars", "min_chars"})
_TOKEN_CHUNKER_KEYS = frozenset({"type", "max_tokens", "overlap_tokens", "tokenizer"})
_SINK_KEYS = frozenset({"type", "database_url", "create_tables"})
_EXPORT_KEYS = frozenset({"text_prepend"})

_LOADER_TYPES = frozenset({"markdown", "filesystem"})
_PARSER_TYPES = frozenset({"markdown", "plaintext", "html", "rst", "auto"})
_CHUNKER_TYPES = frozenset({"heading", "size", "token"})
_SINK_TYPES = frozenset({"sqlalchemy"})
_TEXT_PREPEND_VALUES = frozenset({"none", "title_only", "heading_path", "title_and_heading_path"})
_TOKENIZER_TYPES = frozenset({"whitespace", "character"})


@dataclass(frozen=True, kw_only=True, slots=True)
class MarkdownLoaderConfig:
    type: Literal["markdown"] = "markdown"
    glob_pattern: str = "**/*.md"


@dataclass(frozen=True, kw_only=True, slots=True)
class FileSystemLoaderConfig:
    type: Literal["filesystem"] = "filesystem"
    include_globs: tuple[str, ...] = ("**/*.md", "**/*.txt", "**/*.html", "**/*.htm")
    exclude_globs: tuple[str, ...] = ()
    hidden_policy: Literal["skip", "include"] = "skip"
    symlink_policy: Literal["follow", "skip"] = "follow"
    encoding: str = "utf-8"
    encoding_errors: str = "strict"


@dataclass(frozen=True, kw_only=True, slots=True)
class MarkdownParserConfig:
    type: Literal["markdown"] = "markdown"


@dataclass(frozen=True, kw_only=True, slots=True)
class PlainTextParserConfig:
    type: Literal["plaintext"] = "plaintext"


@dataclass(frozen=True, kw_only=True, slots=True)
class HtmlParserConfig:
    type: Literal["html"] = "html"


@dataclass(frozen=True, kw_only=True, slots=True)
class RstParserConfig:
    type: Literal["rst"] = "rst"


@dataclass(frozen=True, kw_only=True, slots=True)
class AutoParserConfig:
    type: Literal["auto"] = "auto"


@dataclass(frozen=True, kw_only=True, slots=True)
class HeadingChunkerConfig:
    type: Literal["heading"] = "heading"


@dataclass(frozen=True, kw_only=True, slots=True)
class SizeChunkerConfig:
    type: Literal["size"] = "size"
    max_chars: int = 1500
    overlap_chars: int = 0
    min_chars: int = 0


@dataclass(frozen=True, kw_only=True, slots=True)
class TokenChunkerConfig:
    type: Literal["token"] = "token"
    max_tokens: int = 512
    overlap_tokens: int = 0
    tokenizer: str = "whitespace"


ChunkerConfig = HeadingChunkerConfig | SizeChunkerConfig | TokenChunkerConfig


@dataclass(frozen=True, kw_only=True, slots=True)
class SQLAlchemySinkConfig:
    type: Literal["sqlalchemy"] = "sqlalchemy"
    database_url: str
    create_tables: bool = True


@dataclass(frozen=True, kw_only=True, slots=True)
class ExportConfig:
    text_prepend: str = "title_and_heading_path"


@dataclass(frozen=True, kw_only=True, slots=True)
class DocPrepConfig:
    source: str | None = None
    json: bool | None = None
    loader: MarkdownLoaderConfig | FileSystemLoaderConfig | None = None
    parser: (
        MarkdownParserConfig
        | PlainTextParserConfig
        | HtmlParserConfig
        | RstParserConfig
        | AutoParserConfig
        | None
    ) = None
    chunkers: tuple[ChunkerConfig, ...] | None = None
    sink: SQLAlchemySinkConfig | None = None
    export: ExportConfig | None = None
    config_path: Path | None = None

    def resolved_source(self) -> str | None:
        if self.source is None:
            return None
        if self.config_path is None or Path(self.source).is_absolute():
            return self.source
        return str(self.config_path.parent / self.source)


def discover_config_path(*, start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    while True:
        candidate = current / _CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def load_config(path: str | Path) -> DocPrepConfig:
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise ConfigError(f"{config_path}: config file not found")
    try:
        with open(config_path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{config_path}: invalid TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"{config_path}: cannot read config file: {exc}") from exc
    return _parse_raw(raw, config_path)


def load_discovered_config(
    *,
    explicit_path: str | Path | None = None,
    start: Path | None = None,
) -> DocPrepConfig | None:
    if explicit_path is not None:
        return load_config(explicit_path)
    found = discover_config_path(start=start)
    if found is None:
        return None
    return load_config(found)


def _parse_raw(raw: dict[str, Any], config_path: Path) -> DocPrepConfig:
    _check_unknown_keys(raw, _ROOT_KEYS, str(config_path), "root")

    source = raw.get("source")
    if source is not None and not isinstance(source, str):
        raise ConfigError(
            f"{config_path}: root.source: expected string, got {type(source).__name__}"
        )

    json_val = raw.get("json")
    if json_val is not None and not isinstance(json_val, bool):
        raise ConfigError(
            f"{config_path}: root.json: expected boolean, got {type(json_val).__name__}"
        )

    loader = _parse_loader(raw.get("loader"), config_path)
    parser = _parse_parser(raw.get("parser"), config_path)
    chunkers = _parse_chunkers(raw.get("chunkers"), config_path)
    sink = _parse_sink(raw.get("sink"), config_path)
    export = _parse_export(raw.get("export"), config_path)

    return DocPrepConfig(
        source=source,
        json=json_val,
        loader=loader,
        parser=parser,
        chunkers=chunkers,
        sink=sink,
        export=export,
        config_path=config_path,
    )


def _parse_loader(
    raw: Any, config_path: Path
) -> MarkdownLoaderConfig | FileSystemLoaderConfig | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path}: loader: expected table, got {type(raw).__name__}")
    _check_unknown_keys(raw, _LOADER_KEYS, str(config_path), "loader")
    typ = _require_type(raw, _LOADER_TYPES, str(config_path), "loader")
    if typ == "markdown":
        glob_pattern = raw.get("glob_pattern", "**/*.md")
        if not isinstance(glob_pattern, str):
            raise ConfigError(
                f"{config_path}: loader.glob_pattern: expected string, "
                f"got {type(glob_pattern).__name__}"
            )
        return MarkdownLoaderConfig(glob_pattern=glob_pattern)
    if typ == "filesystem":
        include_globs = _parse_glob_list(
            raw.get("include_globs", ["**/*.md", "**/*.txt", "**/*.html", "**/*.htm", "**/*.rst"]),
            config_path,
            "loader.include_globs",
        )
        exclude_globs = _parse_glob_list(
            raw.get("exclude_globs", []),
            config_path,
            "loader.exclude_globs",
        )

        hidden_policy = raw.get("hidden_policy", "skip")
        if hidden_policy not in {"skip", "include"}:
            raise ConfigError(
                f"{config_path}: loader.hidden_policy: "
                f"expected one of include, skip, got {hidden_policy!r}"
            )

        symlink_policy = raw.get("symlink_policy", "follow")
        if symlink_policy not in {"follow", "skip"}:
            raise ConfigError(
                f"{config_path}: loader.symlink_policy: "
                f"expected one of follow, skip, got {symlink_policy!r}"
            )

        encoding = raw.get("encoding", "utf-8")
        if not isinstance(encoding, str):
            raise ConfigError(
                f"{config_path}: loader.encoding: expected string, got {type(encoding).__name__}"
            )

        encoding_errors = raw.get("encoding_errors", "strict")
        if encoding_errors not in {"strict", "replace", "ignore"}:
            raise ConfigError(
                f"{config_path}: loader.encoding_errors: expected one of ignore, replace, strict, "
                f"got {encoding_errors!r}"
            )

        return FileSystemLoaderConfig(
            include_globs=include_globs,
            exclude_globs=exclude_globs,
            hidden_policy=hidden_policy,
            symlink_policy=symlink_policy,
            encoding=encoding,
            encoding_errors=encoding_errors,
        )
    raise ConfigError(f"{config_path}: loader: unsupported type '{typ}'")  # pragma: no cover


def _parse_parser(
    raw: Any, config_path: Path
) -> (
    MarkdownParserConfig
    | PlainTextParserConfig
    | HtmlParserConfig
    | RstParserConfig
    | AutoParserConfig
    | None
):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path}: parser: expected table, got {type(raw).__name__}")
    _check_unknown_keys(raw, _PARSER_KEYS, str(config_path), "parser")
    typ = _require_type(raw, _PARSER_TYPES, str(config_path), "parser")
    if typ == "markdown":
        return MarkdownParserConfig()
    if typ == "plaintext":
        return PlainTextParserConfig()
    if typ == "html":
        return HtmlParserConfig()
    if typ == "rst":
        return RstParserConfig()
    if typ == "auto":
        return AutoParserConfig()
    raise ConfigError(f"{config_path}: parser: unsupported type '{typ}'")  # pragma: no cover


def _parse_glob_list(raw: Any, config_path: Path, field_name: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ConfigError(
            f"{config_path}: {field_name}: expected array of strings, got {type(raw).__name__}"
        )
    values: list[str] = []
    for i, value in enumerate(raw):
        if not isinstance(value, str):
            raise ConfigError(
                f"{config_path}: {field_name}[{i}]: expected string, got {type(value).__name__}"
            )
        values.append(value)
    return tuple(values)


def _parse_chunkers(raw: Any, config_path: Path) -> tuple[ChunkerConfig, ...] | None:
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise ConfigError(
            f"{config_path}: chunkers: expected array of tables, got {type(raw).__name__}"
        )
    configs: list[ChunkerConfig] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ConfigError(
                f"{config_path}: chunkers[{i}]: expected table, got {type(item).__name__}"
            )
        typ = _require_type(item, _CHUNKER_TYPES, str(config_path), f"chunkers[{i}]")
        if typ == "heading":
            _check_unknown_keys(item, _HEADING_CHUNKER_KEYS, str(config_path), f"chunkers[{i}]")
            configs.append(HeadingChunkerConfig())
        elif typ == "size":
            _check_unknown_keys(item, _SIZE_CHUNKER_KEYS, str(config_path), f"chunkers[{i}]")
            max_chars = item.get("max_chars", 1500)
            if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
                raise ConfigError(
                    f"{config_path}: chunkers[{i}].max_chars: expected integer >= 1, "
                    f"got {max_chars!r}"
                )
            overlap_chars = item.get("overlap_chars", 0)
            if (
                isinstance(overlap_chars, bool)
                or not isinstance(overlap_chars, int)
                or overlap_chars < 0
            ):
                raise ConfigError(
                    f"{config_path}: chunkers[{i}].overlap_chars: expected integer >= 0, "
                    f"got {overlap_chars!r}"
                )
            min_chars = item.get("min_chars", 0)
            if isinstance(min_chars, bool) or not isinstance(min_chars, int) or min_chars < 0:
                raise ConfigError(
                    f"{config_path}: chunkers[{i}].min_chars: expected integer >= 0, "
                    f"got {min_chars!r}"
                )
            if overlap_chars >= max_chars:
                raise ConfigError(
                    f"{config_path}: chunkers[{i}].overlap_chars: expected integer < max_chars "
                    f"({max_chars}), got {overlap_chars!r}"
                )
            configs.append(
                SizeChunkerConfig(
                    max_chars=max_chars,
                    overlap_chars=overlap_chars,
                    min_chars=min_chars,
                )
            )
        elif typ == "token":
            _check_unknown_keys(item, _TOKEN_CHUNKER_KEYS, str(config_path), f"chunkers[{i}]")
            max_tokens = item.get("max_tokens", 512)
            if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
                raise ConfigError(
                    f"{config_path}: chunkers[{i}].max_tokens: expected integer >= 1, "
                    f"got {max_tokens!r}"
                )
            overlap_tokens = item.get("overlap_tokens", 0)
            if (
                isinstance(overlap_tokens, bool)
                or not isinstance(overlap_tokens, int)
                or overlap_tokens < 0
            ):
                raise ConfigError(
                    f"{config_path}: chunkers[{i}].overlap_tokens: expected integer >= 0, "
                    f"got {overlap_tokens!r}"
                )
            if overlap_tokens >= max_tokens:
                raise ConfigError(
                    f"{config_path}: chunkers[{i}].overlap_tokens: expected integer < max_tokens "
                    f"({max_tokens}), got {overlap_tokens!r}"
                )
            tokenizer = item.get("tokenizer", "whitespace")
            if not isinstance(tokenizer, str):
                raise ConfigError(
                    f"{config_path}: chunkers[{i}].tokenizer: expected string, "
                    f"got {type(tokenizer).__name__}"
                )
            if tokenizer not in _TOKENIZER_TYPES:
                values = ", ".join(sorted(_TOKENIZER_TYPES))
                raise ConfigError(
                    f"{config_path}: chunkers[{i}].tokenizer: expected one of {values}, "
                    f"got {tokenizer!r}"
                )
            configs.append(
                TokenChunkerConfig(
                    max_tokens=max_tokens,
                    overlap_tokens=overlap_tokens,
                    tokenizer=tokenizer,
                )
            )
        else:
            raise ConfigError(  # pragma: no cover
                f"{config_path}: chunkers[{i}]: unsupported type '{typ}'"
            )
    return tuple(configs)


def _parse_sink(raw: Any, config_path: Path) -> SQLAlchemySinkConfig | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path}: sink: expected table, got {type(raw).__name__}")
    _check_unknown_keys(raw, _SINK_KEYS, str(config_path), "sink")
    typ = _require_type(raw, _SINK_TYPES, str(config_path), "sink")
    if typ == "sqlalchemy":
        if "database_url" not in raw:
            raise ConfigError(
                f"{config_path}: sink: missing required key 'database_url' for type 'sqlalchemy'"
            )
        db_url = raw["database_url"]
        if not isinstance(db_url, str):
            raise ConfigError(
                f"{config_path}: sink.database_url: expected string, got {type(db_url).__name__}"
            )
        create_tables = raw.get("create_tables", True)
        if not isinstance(create_tables, bool):
            raise ConfigError(
                f"{config_path}: sink.create_tables: expected boolean, "
                f"got {type(create_tables).__name__}"
            )
        return SQLAlchemySinkConfig(database_url=db_url, create_tables=create_tables)
    raise ConfigError(f"{config_path}: sink: unsupported type '{typ}'")  # pragma: no cover


def _parse_export(raw: Any, config_path: Path) -> ExportConfig | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path}: export: expected table, got {type(raw).__name__}")
    _check_unknown_keys(raw, _EXPORT_KEYS, str(config_path), "export")
    text_prepend = raw.get("text_prepend", "title_and_heading_path")
    if not isinstance(text_prepend, str):
        raise ConfigError(
            f"{config_path}: export.text_prepend: "
            f"expected string, got {type(text_prepend).__name__}"
        )
    if text_prepend not in _TEXT_PREPEND_VALUES:
        values = ", ".join(sorted(_TEXT_PREPEND_VALUES))
        raise ConfigError(
            f"{config_path}: export.text_prepend: expected one of {values}, got {text_prepend!r}"
        )
    return ExportConfig(text_prepend=text_prepend)


def _check_unknown_keys(
    raw: dict[str, Any], allowed: frozenset[str], path: str, location: str
) -> None:
    unknown = set(raw.keys()) - allowed
    if unknown:
        sorted_unknown = ", ".join(sorted(unknown))
        sorted_allowed = ", ".join(sorted(allowed))
        raise ConfigError(
            f"{path}: {location}: unknown key(s) {sorted_unknown}; allowed: {sorted_allowed}"
        )


def _require_type(raw: dict[str, Any], supported: frozenset[str], path: str, location: str) -> str:
    if "type" not in raw:
        raise ConfigError(f"{path}: {location}: missing required key 'type'")
    typ = raw["type"]
    if not isinstance(typ, str):
        raise ConfigError(f"{path}: {location}.type: expected string, got {type(typ).__name__}")
    if typ not in supported:
        supported_str = ", ".join(sorted(supported))
        raise ConfigError(
            f"{path}: {location}: unknown component type '{typ}'; supported: {supported_str}"
        )
    return typ
