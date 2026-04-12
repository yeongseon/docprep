from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from unittest.mock import patch

import pytest

from docprep.adapters.protocol import Adapter
from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker
from docprep.chunkers.token import TokenChunker
from docprep.loaders.filesystem import FileSystemLoader
from docprep.loaders.markdown import MarkdownLoader
from docprep.models.domain import Document
from docprep.parsers.html import HtmlParser
from docprep.parsers.markdown import MarkdownParser
from docprep.parsers.multi import MultiFormatParser
from docprep.parsers.plaintext import PlainTextParser
from docprep.plugins import (
    CHUNKER_GROUP,
    LOADER_GROUP,
    PARSER_GROUP,
    SINK_GROUP,
    discover_entry_points,
)
from docprep.registry import (
    BUILTIN_CHUNKERS,
    BUILTIN_LOADERS,
    BUILTIN_PARSERS,
    BUILTIN_SINKS,
    get_all_chunkers,
    get_all_loaders,
    get_all_parsers,
    get_all_sinks,
    resolve_component,
)
from docprep.sinks.sqlalchemy import SQLAlchemySink


class _MockEntryPoint:
    def __init__(
        self, name: str, value: str, loaded: object | None = None, error: Exception | None = None
    ):
        self.name = name
        self.value = value
        self._loaded = loaded
        self._error = error

    def load(self) -> object:
        if self._error is not None:
            raise self._error
        return self._loaded


def test_discover_entry_points_loads_plugins_and_warns_on_failures(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class PluginLoader:
        pass

    ok = _MockEntryPoint("ok", "example:PluginLoader", loaded=PluginLoader)
    bad = _MockEntryPoint("broken", "example:BrokenLoader", error=ImportError("missing dependency"))

    with patch("docprep.plugins.importlib.metadata.entry_points", return_value=[ok, bad]):
        with pytest.warns(RuntimeWarning, match="Failed to load plugin 'broken'"):
            discovered = discover_entry_points(LOADER_GROUP)

    assert discovered == {"ok": PluginLoader}
    assert "Failed to load plugin 'broken'" in caplog.text


def test_discover_entry_points_warns_when_lookup_fails() -> None:
    with patch("docprep.plugins.importlib.metadata.entry_points", side_effect=RuntimeError("boom")):
        with pytest.warns(RuntimeWarning, match="Unable to discover plugins"):
            discovered = discover_entry_points(PARSER_GROUP)

    assert discovered == {}


def test_builtin_entry_points_are_discoverable_when_installed() -> None:
    discovered = discover_entry_points(LOADER_GROUP)
    if not discovered:
        pytest.skip("Entry points for this distribution are unavailable in this test environment")

    assert discovered["markdown"] is MarkdownLoader
    assert discovered["filesystem"] is FileSystemLoader


def test_get_all_component_helpers_include_builtin_components() -> None:
    loaders = get_all_loaders()
    parsers = get_all_parsers()
    chunkers = get_all_chunkers()
    sinks = get_all_sinks()

    assert set(BUILTIN_LOADERS).issubset(set(loaders))
    assert set(BUILTIN_PARSERS).issubset(set(parsers))
    assert set(BUILTIN_CHUNKERS).issubset(set(chunkers))
    assert set(BUILTIN_SINKS).issubset(set(sinks))
    assert loaders["markdown"] is MarkdownLoader
    assert loaders["filesystem"] is FileSystemLoader
    assert parsers["markdown"] is MarkdownParser
    assert parsers["plaintext"] is PlainTextParser
    assert parsers["html"] is HtmlParser
    assert parsers["auto"] is MultiFormatParser
    assert chunkers["heading"] is HeadingChunker
    assert chunkers["size"] is SizeChunker
    assert chunkers["token"] is TokenChunker
    assert sinks["sqlalchemy"] is SQLAlchemySink


def test_resolve_component_prefers_builtin_over_plugin() -> None:
    fake_plugin = object()
    with patch("docprep.registry.discover_entry_points", return_value={"markdown": fake_plugin}):
        resolved = resolve_component(LOADER_GROUP, "markdown")

    assert resolved is MarkdownLoader


def test_resolve_component_finds_plugin_when_name_not_builtin() -> None:
    custom = object()
    with patch("docprep.registry.discover_entry_points", return_value={"custom": custom}):
        resolved = resolve_component(CHUNKER_GROUP, "custom")

    assert resolved is custom


def test_resolve_component_raises_actionable_error_for_unknown_component() -> None:
    with patch("docprep.registry.discover_entry_points", return_value={}):
        with pytest.raises(LookupError) as exc_info:
            resolve_component(SINK_GROUP, "missing")

    message = str(exc_info.value)
    assert "Unknown component 'missing'" in message
    assert "Available components" in message
    assert "entry point" in message


def test_adapter_protocol_runtime_check() -> None:
    class CustomAdapter:
        def convert(self, source: str | Path) -> Iterable[Document]:
            del source
            return []

        @property
        def supported_extensions(self) -> frozenset[str]:
            return frozenset({".pdf", ".docx"})

    assert isinstance(CustomAdapter(), Adapter)
