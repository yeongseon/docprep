from __future__ import annotations

from html.parser import HTMLParser
from pathlib import PurePosixPath
import re

from ..chunkers._markdown import extract_structural_annotations
from ..exceptions import ParseError
from ..ids import document_id
from ..loaders.types import LoadedSource
from ..metadata import normalize_metadata
from ..models.domain import Document

_WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")


class _HtmlToMarkdownParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self.title_text: str | None = None
        self.first_h1: str | None = None

        self._ignored_depth = 0
        self._in_title = False
        self._title_buffer: list[str] = []

        self._heading_level: int | None = None
        self._heading_buffer: list[str] = []

        self._in_paragraph = False
        self._paragraph_buffer: list[str] = []

        self._in_list_item = False
        self._list_item_buffer: list[str] = []

        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._current_table_row: list[str] | None = None
        self._in_table_cell = False
        self._table_cell_buffer: list[str] = []

        self._code_depth = 0
        self._pre_depth = 0
        self._code_buffer: list[str] = []

        self._free_text_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth > 0:
            return

        if tag == "title":
            self._in_title = True
            self._title_buffer = []
            return

        if tag == "br":
            self._append_inline_newline()
            return

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush_free_text()
            self._heading_level = int(tag[1])
            self._heading_buffer = []
            return

        if tag == "p":
            self._flush_free_text()
            self._in_paragraph = True
            self._paragraph_buffer = []
            return

        if tag == "li":
            self._flush_free_text()
            self._in_list_item = True
            self._list_item_buffer = []
            return

        if tag == "table":
            self._flush_free_text()
            self._in_table = True
            self._table_rows = []
            self._current_table_row = None
            self._in_table_cell = False
            self._table_cell_buffer = []
            return

        if tag == "tr" and self._in_table:
            self._current_table_row = []
            return

        if tag in {"th", "td"} and self._in_table and self._current_table_row is not None:
            self._in_table_cell = True
            self._table_cell_buffer = []
            return

        if tag in {"pre", "code"}:
            self._flush_free_text()
            if self._code_depth == 0 and self._pre_depth == 0:
                self._code_buffer = []
            if tag == "pre":
                self._pre_depth += 1
            else:
                self._code_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored_depth > 0:
            self._ignored_depth -= 1
            return
        if self._ignored_depth > 0:
            return

        if tag == "title" and self._in_title:
            self._in_title = False
            title = self._normalize_block_text("".join(self._title_buffer))
            if title and self.title_text is None:
                self.title_text = title
            self._title_buffer = []
            return

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._heading_level is not None:
            text = self._normalize_block_text("".join(self._heading_buffer))
            if text:
                prefix = "#" * self._heading_level
                self._append_block(f"{prefix} {text}")
                if self._heading_level == 1 and self.first_h1 is None:
                    self.first_h1 = text
            self._heading_level = None
            self._heading_buffer = []
            return

        if tag == "p" and self._in_paragraph:
            text = self._normalize_block_text("".join(self._paragraph_buffer))
            if text:
                self._append_block(text)
            self._in_paragraph = False
            self._paragraph_buffer = []
            return

        if tag == "li" and self._in_list_item:
            text = self._normalize_block_text("".join(self._list_item_buffer))
            if text:
                self._append_block(f"- {text}")
            self._in_list_item = False
            self._list_item_buffer = []
            return

        if tag in {"th", "td"} and self._in_table and self._in_table_cell:
            text = self._normalize_block_text("".join(self._table_cell_buffer))
            if self._current_table_row is not None:
                self._current_table_row.append(text)
            self._in_table_cell = False
            self._table_cell_buffer = []
            return

        if tag == "tr" and self._in_table:
            if self._current_table_row:
                self._table_rows.append(self._current_table_row)
            self._current_table_row = None
            return

        if tag == "table" and self._in_table:
            table_markdown = self._table_to_markdown(self._table_rows)
            if table_markdown:
                self._append_block(table_markdown)
            self._in_table = False
            self._table_rows = []
            self._current_table_row = None
            self._in_table_cell = False
            self._table_cell_buffer = []
            return

        if tag == "pre" and self._pre_depth > 0:
            self._pre_depth -= 1
        elif tag == "code" and self._code_depth > 0:
            self._code_depth -= 1

        if tag in {"pre", "code"} and self._pre_depth == 0 and self._code_depth == 0:
            code_text = "".join(self._code_buffer).strip("\n")
            self._append_block(f"```\n{code_text}\n```")
            self._code_buffer = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth > 0:
            return
        if self._in_title:
            self._title_buffer.append(data)
            return
        if self._in_table and self._in_table_cell:
            self._table_cell_buffer.append(data)
            return
        if self._pre_depth > 0 or self._code_depth > 0:
            self._code_buffer.append(data)
            return
        if self._heading_level is not None:
            self._heading_buffer.append(data)
            return
        if self._in_paragraph:
            self._paragraph_buffer.append(data)
            return
        if self._in_list_item:
            self._list_item_buffer.append(data)
            return
        self._free_text_buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush_free_text()

    def _append_inline_newline(self) -> None:
        if self._pre_depth > 0 or self._code_depth > 0:
            self._code_buffer.append("\n")
            return
        if self._heading_level is not None:
            self._heading_buffer.append("\n")
            return
        if self._in_paragraph:
            self._paragraph_buffer.append("\n")
            return
        if self._in_list_item:
            self._list_item_buffer.append("\n")
            return
        self._free_text_buffer.append("\n")

    def _flush_free_text(self) -> None:
        if not self._free_text_buffer:
            return
        text = self._normalize_block_text("".join(self._free_text_buffer))
        if text:
            self._append_block(text)
        self._free_text_buffer = []

    def _append_block(self, block: str) -> None:
        if block:
            self.blocks.append(block)

    def _normalize_block_text(self, text: str) -> str:
        lines = text.splitlines()
        normalized_lines: list[str] = []
        for line in lines:
            compact = _WHITESPACE_RE.sub(" ", line).strip()
            if compact:
                normalized_lines.append(compact)
        return "\n".join(normalized_lines)

    def _table_to_markdown(self, rows: list[list[str]]) -> str:
        if not rows:
            return ""
        header = rows[0]
        column_count = len(header)
        if column_count == 0:
            return ""

        separator = ["---"] * column_count
        markdown_lines = [
            f"| {' | '.join(header)} |",
            f"| {' | '.join(separator)} |",
        ]
        for row in rows[1:]:
            normalized = row[:column_count] + [""] * max(0, column_count - len(row))
            markdown_lines.append(f"| {' | '.join(normalized)} |")
        return "\n".join(markdown_lines)


class HtmlParser:
    def parse(self, loaded_source: LoadedSource) -> Document:
        parser = _HtmlToMarkdownParser()
        try:
            parser.feed(loaded_source.raw_text)
            parser.close()
        except Exception as exc:
            raise ParseError(
                f"Failed to parse HTML from {loaded_source.source_uri}: {exc}"
            ) from exc

        title = parser.title_text or parser.first_h1 or self._source_stem(loaded_source.source_uri)
        body_markdown = "\n\n".join(parser.blocks)
        annotations = extract_structural_annotations(body_markdown)
        normalized_source_meta = normalize_metadata(
            loaded_source.source_metadata,
            source=loaded_source.source_uri,
            field_name="source_metadata",
        )

        return Document(
            id=document_id(loaded_source.source_uri),
            source_uri=loaded_source.source_uri,
            title=title,
            source_checksum=loaded_source.checksum,
            source_type="html",
            frontmatter={},
            source_metadata=normalized_source_meta,
            body_markdown=body_markdown,
            structural_annotations=annotations,
        )

    def _source_stem(self, source_uri: str) -> str:
        source_path = source_uri[5:] if source_uri.startswith("file:") else source_uri
        return PurePosixPath(source_path).stem
