from __future__ import annotations

from pathlib import Path

import pytest

from docprep.config import (
    DocPrepConfig,
    ExportConfig,
    SQLAlchemySinkConfig,
    load_config,
    load_discovered_config,
)
from docprep.exceptions import ConfigError


def _write_config(tmp_path: Path, content: str, *, name: str = "docprep.toml") -> Path:
    path = tmp_path / name
    _ = path.write_text(content, encoding="utf-8")
    return path


def test_env_overrides_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = _write_config(tmp_path, "source = 'from-config'\n")
    monkeypatch.setenv("DOCPREP_SOURCE", "from-env")

    config = load_config(config_path)

    assert config.source == "from-env"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [("true", True), ("false", False), ("1", True), ("0", False)],
)
def test_env_overrides_json_accepts_boolean_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected: bool,
) -> None:
    config_path = _write_config(tmp_path, "json = false\n")
    monkeypatch.setenv("DOCPREP_JSON", raw_value)

    config = load_config(config_path)

    assert config.json is expected


def test_env_sink_database_url_creates_sink_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_config(tmp_path, "")
    monkeypatch.setenv("DOCPREP_SINK__DATABASE_URL", "sqlite:///env.db")

    config = load_config(config_path)

    assert config.sink == SQLAlchemySinkConfig(database_url="sqlite:///env.db", create_tables=True)


def test_env_sink_database_url_overrides_existing_sink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_config(
        tmp_path,
        """
[sink]
type = "sqlalchemy"
database_url = "sqlite:///from-config.db"
create_tables = false
""".strip()
        + "\n",
    )
    monkeypatch.setenv("DOCPREP_SINK__DATABASE_URL", "sqlite:///from-env.db")

    config = load_config(config_path)

    assert config.sink == SQLAlchemySinkConfig(
        database_url="sqlite:///from-env.db",
        create_tables=False,
    )


@pytest.mark.parametrize(("raw_value", "expected"), [("true", True), ("0", False)])
def test_env_sink_create_tables_overrides_existing_sink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected: bool,
) -> None:
    config_path = _write_config(
        tmp_path,
        """
[sink]
type = "sqlalchemy"
database_url = "sqlite:///from-config.db"
create_tables = false
""".strip()
        + "\n",
    )
    monkeypatch.setenv("DOCPREP_SINK__CREATE_TABLES", raw_value)

    config = load_config(config_path)

    assert config.sink == SQLAlchemySinkConfig(
        database_url="sqlite:///from-config.db",
        create_tables=expected,
    )


def test_env_export_text_prepend_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = _write_config(
        tmp_path,
        """
[export]
text_prepend = "title_and_heading_path"
include_annotations = true
""".strip()
        + "\n",
    )
    monkeypatch.setenv("DOCPREP_EXPORT__TEXT_PREPEND", "heading_path")

    config = load_config(config_path)

    assert config.export == ExportConfig(text_prepend="heading_path", include_annotations=True)


def test_env_export_include_annotations_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_config(
        tmp_path,
        """
[export]
text_prepend = "title_only"
include_annotations = false
""".strip()
        + "\n",
    )
    monkeypatch.setenv("DOCPREP_EXPORT__INCLUDE_ANNOTATIONS", "1")

    config = load_config(config_path)

    assert config.export == ExportConfig(text_prepend="title_only", include_annotations=True)


def test_env_invalid_boolean_raises_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_config(tmp_path, "")
    monkeypatch.setenv("DOCPREP_JSON", "yes")

    with pytest.raises(ConfigError, match="root.json: expected boolean, got str"):
        _ = load_config(config_path)


def test_env_invalid_text_prepend_raises_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_config(tmp_path, "")
    monkeypatch.setenv("DOCPREP_EXPORT__TEXT_PREPEND", "all")

    with pytest.raises(ConfigError, match="export.text_prepend: expected one of"):
        _ = load_config(config_path)


def test_unknown_docprep_env_vars_are_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCPREP_UNUSED", "value")

    config = load_discovered_config(start=tmp_path)

    assert config is None


def test_discovered_config_returns_env_only_config_when_supported_env_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCPREP_SOURCE", "docs")

    config = load_discovered_config(start=tmp_path)

    assert config == DocPrepConfig(source="docs")
