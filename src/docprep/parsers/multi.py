from __future__ import annotations

from ..exceptions import ParseError
from ..loaders.types import LoadedSource
from ..models.domain import Document
from .html import HtmlParser
from .markdown import MarkdownParser
from .plaintext import PlainTextParser
from .protocol import Parser
from .rst import RstParser


class MultiFormatParser:
    def __init__(self, parsers: dict[str, Parser] | None = None) -> None:
        self._parsers = parsers or {
            "text/markdown": MarkdownParser(),
            "text/plain": PlainTextParser(),
            "text/html": HtmlParser(),
            "text/x-rst": RstParser(),
        }

    def parse(self, loaded_source: LoadedSource) -> Document:
        parser = self._parsers.get(loaded_source.media_type)
        if parser is None:
            raise ParseError(f"No parser for media type: {loaded_source.media_type}")
        return parser.parse(loaded_source)
