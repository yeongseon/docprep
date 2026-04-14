from __future__ import annotations

from pathlib import Path

import pytest

from docprep.config import (
    AutoParserConfig,
    DocPrepConfig,
    ExportConfig,
    FileSystemLoaderConfig,
    HeadingChunkerConfig,
    HtmlParserConfig,
    MarkdownLoaderConfig,
    MarkdownParserConfig,
    PlainTextParserConfig,
    SizeChunkerConfig,
    SQLAlchemySinkConfig,
    TokenChunkerConfig,
    discover_config_path,
    load_config,
    load_discovered_config,
)
from docprep.exceptions import ConfigError


def _write_config(tmp_path: Path, content: str, *, name: str = "docprep.toml") -> Path:
    path = tmp_path / name
    _ = path.write_text(content, encoding="utf-8")
    return path


def test_config_dataclass_defaults_are_expected() -> None:
    assert MarkdownLoaderConfig() == MarkdownLoaderConfig(type="markdown", glob_pattern="**/*.md")
    assert FileSystemLoaderConfig() == FileSystemLoaderConfig(
        type="filesystem",
        include_globs=("**/*.md", "**/*.txt", "**/*.html", "**/*.htm", "**/*.rst"),
        exclude_globs=(),
        hidden_policy="skip",
        symlink_policy="follow",
        encoding="utf-8",
        encoding_errors="strict",
    )
    assert MarkdownParserConfig() == MarkdownParserConfig(type="markdown")
    assert PlainTextParserConfig() == PlainTextParserConfig(type="plaintext")
    assert HtmlParserConfig() == HtmlParserConfig(type="html")
    assert AutoParserConfig() == AutoParserConfig(type="auto")
    assert HeadingChunkerConfig() == HeadingChunkerConfig(type="heading")
    assert SizeChunkerConfig() == SizeChunkerConfig(
        type="size",
        max_chars=1500,
        overlap_chars=0,
        min_chars=0,
    )
    assert TokenChunkerConfig() == TokenChunkerConfig(
        type="token",
        max_tokens=512,
        overlap_tokens=0,
        tokenizer="whitespace",
    )
    assert SQLAlchemySinkConfig(database_url="sqlite:///docs.db") == SQLAlchemySinkConfig(
        type="sqlalchemy",
        database_url="sqlite:///docs.db",
        create_tables=True,
    )
    assert ExportConfig() == ExportConfig(
        text_prepend="title_and_heading_path",
        include_annotations=False,
    )


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        (
            DocPrepConfig(source="docs", config_path=Path("/tmp/project/docprep.toml")),
            "/tmp/project/docs",
        ),
        (
            DocPrepConfig(source="/tmp/docs", config_path=Path("/tmp/project/docprep.toml")),
            "/tmp/docs",
        ),
        (DocPrepConfig(source=None, config_path=Path("/tmp/project/docprep.toml")), None),
        (DocPrepConfig(source="docs", config_path=None), "docs"),
    ],
)
def test_docprep_config_resolved_source_handles_common_cases(
    config: DocPrepConfig, expected: str | None
) -> None:
    assert config.resolved_source() == expected


def test_discover_config_path_finds_file_in_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_config(tmp_path, "source = 'docs'\n")
    monkeypatch.chdir(tmp_path)

    assert discover_config_path() == config_path


def test_discover_config_path_walks_up_parent_directories(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, "source = 'docs'\n")
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)

    assert discover_config_path(start=nested) == config_path


def test_discover_config_path_returns_none_when_missing(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    assert discover_config_path(start=nested) is None


def test_load_config_loads_valid_toml(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
source = "docs"
json = true

[loader]
type = "markdown"
glob_pattern = "content/**/*.md"

[parser]
type = "markdown"

[[chunkers]]
type = "heading"

[[chunkers]]
type = "size"
max_chars = 250
overlap_chars = 25
min_chars = 10

[[chunkers]]
type = "token"
max_tokens = 64
overlap_tokens = 8
tokenizer = "character"

[sink]
type = "sqlalchemy"
database_url = "sqlite:///docs.db"
create_tables = false
""".strip()
        + "\n",
    )

    config = load_config(config_path)

    assert config == DocPrepConfig(
        source="docs",
        json=True,
        loader=MarkdownLoaderConfig(glob_pattern="content/**/*.md"),
        parser=MarkdownParserConfig(),
        chunkers=(
            HeadingChunkerConfig(),
            SizeChunkerConfig(max_chars=250, overlap_chars=25, min_chars=10),
            TokenChunkerConfig(max_tokens=64, overlap_tokens=8, tokenizer="character"),
        ),
        sink=SQLAlchemySinkConfig(database_url="sqlite:///docs.db", create_tables=False),
        config_path=config_path,
    )


def test_load_config_raises_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.toml"

    with pytest.raises(ConfigError, match="config file not found"):
        _ = load_config(missing)


def test_load_config_raises_for_invalid_toml(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, "[loader\ntype = 'markdown'\n")

    with pytest.raises(ConfigError, match="invalid TOML"):
        _ = load_config(config_path)


def test_load_discovered_config_uses_explicit_path(tmp_path: Path) -> None:
    explicit = _write_config(tmp_path, "source = 'explicit'\n", name="explicit.toml")
    _ = _write_config(tmp_path, "source = 'discovered'\n")

    config = load_discovered_config(explicit_path=explicit)

    assert config is not None
    assert config.source == "explicit"
    assert config.config_path == explicit.resolve()


def test_load_discovered_config_finds_discovered_file(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, "source = 'docs'\n")
    nested = tmp_path / "nested"
    nested.mkdir()

    config = load_discovered_config(start=nested)

    assert config is not None
    assert config.config_path == config_path


def test_load_discovered_config_returns_none_when_file_missing(tmp_path: Path) -> None:
    assert load_discovered_config(start=tmp_path) is None


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("unknown = 1\n", r"root: unknown key\(s\) unknown"),
        ("[loader]\ntype = 'markdown'\nextra = 1\n", r"loader: unknown key\(s\) extra"),
        ("[parser]\ntype = 'markdown'\nextra = 1\n", r"parser: unknown key\(s\) extra"),
        (
            "[[chunkers]]\ntype = 'heading'\nextra = 1\n",
            r"chunkers\[0\]: unknown key\(s\) extra",
        ),
        (
            "[sink]\ntype = 'sqlalchemy'\ndatabase_url = 'sqlite://'\nextra = 1\n",
            r"sink: unknown key\(s\) extra",
        ),
    ],
)
def test_load_config_rejects_unknown_keys(tmp_path: Path, content: str, match: str) -> None:
    config_path = _write_config(tmp_path, content)

    with pytest.raises(ConfigError, match=match):
        _ = load_config(config_path)


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("source = 123\n", "root.source: expected string, got int"),
        ("json = 'yes'\n", "root.json: expected boolean, got str"),
        (
            "[loader]\ntype = 'markdown'\nglob_pattern = 123\n",
            "loader.glob_pattern: expected string, got int",
        ),
        (
            "[[chunkers]]\ntype = 'size'\nmax_chars = 'big'\n",
            r"chunkers\[0\]\.max_chars: expected integer >= 1",
        ),
        (
            "[[chunkers]]\ntype = 'size'\nmax_chars = 0\n",
            r"chunkers\[0\]\.max_chars: expected integer >= 1",
        ),
        (
            "[[chunkers]]\ntype = 'size'\noverlap_chars = -1\n",
            r"chunkers\[0\]\.overlap_chars: expected integer >= 0",
        ),
        (
            "[[chunkers]]\ntype = 'size'\nmin_chars = -1\n",
            r"chunkers\[0\]\.min_chars: expected integer >= 0",
        ),
        (
            "[[chunkers]]\ntype = 'size'\nmax_chars = 10\noverlap_chars = 10\n",
            r"chunkers\[0\]\.overlap_chars: expected integer < max_chars",
        ),
        (
            "[[chunkers]]\ntype = 'token'\nmax_tokens = 0\n",
            r"chunkers\[0\]\.max_tokens: expected integer >= 1",
        ),
        (
            "[[chunkers]]\ntype = 'token'\noverlap_tokens = -1\n",
            r"chunkers\[0\]\.overlap_tokens: expected integer >= 0",
        ),
        (
            "[[chunkers]]\ntype = 'token'\nmax_tokens = 10\noverlap_tokens = 10\n",
            r"chunkers\[0\]\.overlap_tokens: expected integer < max_tokens",
        ),
        (
            "[[chunkers]]\ntype = 'token'\ntokenizer = 'bpe'\n",
            r"chunkers\[0\]\.tokenizer: expected one of character, whitespace",
        ),
        (
            "[sink]\ntype = 'sqlalchemy'\ndatabase_url = 123\n",
            "sink.database_url: expected string, got int",
        ),
        (
            "[sink]\ntype = 'sqlalchemy'\ndatabase_url = 'sqlite://'\ncreate_tables = 'yes'\n",
            "sink.create_tables: expected boolean, got str",
        ),
    ],
)
def test_load_config_rejects_type_mismatches(tmp_path: Path, content: str, match: str) -> None:
    config_path = _write_config(tmp_path, content)

    with pytest.raises(ConfigError, match=match):
        _ = load_config(config_path)


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("[loader]\nglob_pattern = '**/*.md'\n", "loader: missing required key 'type'"),
        ("[parser]\n", "parser: missing required key 'type'"),
        ("[[chunkers]]\nmax_chars = 10\n", r"chunkers\[0\]: missing required key 'type'"),
        (
            "[sink]\ntype = 'sqlalchemy'\n",
            "sink: missing required key 'database_url' for type 'sqlalchemy'",
        ),
    ],
)
def test_load_config_rejects_missing_required_keys(
    tmp_path: Path, content: str, match: str
) -> None:
    config_path = _write_config(tmp_path, content)

    with pytest.raises(ConfigError, match=match):
        _ = load_config(config_path)


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("[loader]\ntype = 'html'\n", "loader: unknown component type 'html'"),
        ("[parser]\ntype = 'xml'\n", "parser: unknown component type 'xml'"),
        ("[[chunkers]]\ntype = 'words'\n", r"chunkers\[0\]: unknown component type 'words'"),
        ("[sink]\ntype = 'memory'\n", "sink: unknown component type 'memory'"),
    ],
)
def test_load_config_rejects_unsupported_component_types(
    tmp_path: Path, content: str, match: str
) -> None:
    config_path = _write_config(tmp_path, content)

    with pytest.raises(ConfigError, match=match):
        _ = load_config(config_path)


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ("loader = 'markdown'\n", "loader: expected table, got str"),
        ("parser = 'markdown'\n", "parser: expected table, got str"),
        ("chunkers = 'heading'\n", "chunkers: expected array of tables, got str"),
        ("chunkers = [1]\n", r"chunkers\[0\]: expected table, got int"),
        ("sink = 'sqlite://'\n", "sink: expected table, got str"),
    ],
)
def test_load_config_rejects_invalid_section_types(
    tmp_path: Path, content: str, match: str
) -> None:
    config_path = _write_config(tmp_path, content)

    with pytest.raises(ConfigError, match=match):
        _ = load_config(config_path)


def test_load_config_round_trips_complete_configuration(tmp_path: Path) -> None:
    docs_dir = tmp_path / "content"
    docs_dir.mkdir()
    config_path = _write_config(
        tmp_path,
        """
source = "content"
json = false

[loader]
type = "markdown"
glob_pattern = "guides/**/*.md"

[parser]
type = "markdown"

[[chunkers]]
type = "heading"

[[chunkers]]
type = "size"
max_chars = 321
overlap_chars = 32
min_chars = 8

[[chunkers]]
type = "token"
max_tokens = 128
overlap_tokens = 16
tokenizer = "whitespace"

[sink]
type = "sqlalchemy"
database_url = "sqlite:///roundtrip.db"
create_tables = true
""".strip()
        + "\n",
    )

    config = load_config(config_path)

    assert config.source == "content"
    assert config.resolved_source() == str(docs_dir)
    assert config.json is False
    assert config.loader == MarkdownLoaderConfig(glob_pattern="guides/**/*.md")
    assert config.parser == MarkdownParserConfig()
    assert config.chunkers == (
        HeadingChunkerConfig(),
        SizeChunkerConfig(max_chars=321, overlap_chars=32, min_chars=8),
        TokenChunkerConfig(max_tokens=128, overlap_tokens=16, tokenizer="whitespace"),
    )
    assert config.sink == SQLAlchemySinkConfig(
        database_url="sqlite:///roundtrip.db",
        create_tables=True,
    )
    assert config.config_path == config_path


def test_export_section_parsed(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
[export]
text_prepend = "title_only"
""".strip()
        + "\n",
    )

    config = load_config(config_path)

    assert config.export == ExportConfig(text_prepend="title_only", include_annotations=False)


def test_export_section_parsed_with_include_annotations(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
[export]
text_prepend = "title_only"
include_annotations = true
""".strip()
        + "\n",
    )

    config = load_config(config_path)

    assert config.export == ExportConfig(text_prepend="title_only", include_annotations=True)


def test_export_section_rejects_non_bool_include_annotations(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
[export]
include_annotations = "yes"
""".strip()
        + "\n",
    )

    with pytest.raises(ConfigError, match="export.include_annotations: expected boolean, got str"):
        _ = load_config(config_path)


def test_load_config_rejects_bool_for_max_chars(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, "[[chunkers]]\ntype = 'size'\nmax_chars = true\n")

    with pytest.raises(ConfigError, match=r"chunkers\[0\]\.max_chars: expected integer >= 1"):
        _ = load_config(config_path)


def test_load_config_rejects_bool_for_overlap_and_min_chars(tmp_path: Path) -> None:
    overlap_path = _write_config(
        tmp_path,
        "[[chunkers]]\ntype = 'size'\noverlap_chars = true\n",
        name="overlap.toml",
    )
    min_path = _write_config(
        tmp_path,
        "[[chunkers]]\ntype = 'size'\nmin_chars = true\n",
        name="min.toml",
    )

    with pytest.raises(ConfigError, match=r"chunkers\[0\]\.overlap_chars: expected integer >= 0"):
        _ = load_config(overlap_path)
    with pytest.raises(ConfigError, match=r"chunkers\[0\]\.min_chars: expected integer >= 0"):
        _ = load_config(min_path)


def test_load_config_rejects_bool_for_token_chunker_fields(tmp_path: Path) -> None:
    max_path = _write_config(
        tmp_path,
        "[[chunkers]]\ntype = 'token'\nmax_tokens = true\n",
        name="token-max.toml",
    )
    overlap_path = _write_config(
        tmp_path,
        "[[chunkers]]\ntype = 'token'\noverlap_tokens = true\n",
        name="token-overlap.toml",
    )

    with pytest.raises(ConfigError, match=r"chunkers\[0\]\.max_tokens: expected integer >= 1"):
        _ = load_config(max_path)
    with pytest.raises(ConfigError, match=r"chunkers\[0\]\.overlap_tokens: expected integer >= 0"):
        _ = load_config(overlap_path)


def test_load_config_wraps_os_error_as_config_error(tmp_path: Path) -> None:
    config_path = tmp_path / "docprep.toml"
    _ = config_path.write_text("source = 'docs'\n", encoding="utf-8")
    config_path.chmod(0o000)

    try:
        with pytest.raises(ConfigError, match="cannot read config file"):
            _ = load_config(config_path)
    finally:
        config_path.chmod(0o644)


def test_load_config_empty_file_returns_all_none_config(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, "")

    config = load_config(config_path)

    assert config.source is None
    assert config.json is None
    assert config.loader is None
    assert config.parser is None
    assert config.chunkers is None
    assert config.sink is None
    assert config.export is None
    assert config.config_path == config_path


def test_load_config_parses_filesystem_loader_and_auto_parser(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
[loader]
type = "filesystem"
include_globs = ["content/**/*.md", "content/**/*.txt"]
exclude_globs = ["content/drafts/**"]
hidden_policy = "include"
symlink_policy = "skip"
encoding = "latin-1"
encoding_errors = "replace"

[parser]
type = "auto"
""".strip()
        + "\n",
    )

    config = load_config(config_path)

    assert config.loader == FileSystemLoaderConfig(
        include_globs=("content/**/*.md", "content/**/*.txt"),
        exclude_globs=("content/drafts/**",),
        hidden_policy="include",
        symlink_policy="skip",
        encoding="latin-1",
        encoding_errors="replace",
    )
    assert config.parser == AutoParserConfig()


def test_load_config_rejects_invalid_filesystem_loader_values(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        """
[loader]
type = "filesystem"
include_globs = "**/*.md"
""".strip()
        + "\n",
    )

    with pytest.raises(ConfigError, match="loader.include_globs: expected array of strings"):
        _ = load_config(config_path)


def test_load_config_accepts_plaintext_and_html_parser_types(tmp_path: Path) -> None:
    plaintext_path = _write_config(
        tmp_path, "[parser]\ntype = 'plaintext'\n", name="plaintext.toml"
    )
    html_path = _write_config(tmp_path, "[parser]\ntype = 'html'\n", name="html.toml")

    assert load_config(plaintext_path).parser == PlainTextParserConfig()
    assert load_config(html_path).parser == HtmlParserConfig()
