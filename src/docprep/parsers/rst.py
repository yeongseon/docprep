"""RST parser - converts loaded reStructuredText into Documents."""

from __future__ import annotations

from pathlib import PurePosixPath
import re

from ..chunkers._markdown import extract_structural_annotations
from ..ids import document_id
from ..loaders.types import LoadedSource
from ..metadata import normalize_metadata
from ..models.domain import Document

_FIELD_RE = re.compile(r"^:([^:]+):\s*(.*)$")


class RstParser:
    """Parses a loaded RST source into a Document."""

    def parse(self, loaded_source: LoadedSource) -> Document:
        raw_text = loaded_source.raw_text
        field_list = self._extract_field_list(raw_text)
        body = self._strip_field_list(raw_text)
        body_markdown = self._rst_to_markdown(body)
        annotations = extract_structural_annotations(body_markdown)
        title = self._extract_title(field_list, body, loaded_source.source_uri)
        normalized_meta = normalize_metadata(
            field_list,
            source=loaded_source.source_uri,
            field_name="rst_fields",
        )

        return Document(
            id=document_id(loaded_source.source_uri),
            source_uri=loaded_source.source_uri,
            title=title,
            source_checksum=loaded_source.checksum,
            source_type="rst",
            frontmatter=normalized_meta,
            source_metadata={},
            body_markdown=body_markdown,
            structural_annotations=annotations,
        )

    def _extract_field_list(self, raw_text: str) -> dict[str, str]:
        lines = raw_text.splitlines()
        _, end_index, parsed_any = self._field_list_bounds(lines)
        if not parsed_any:
            return {}

        fields: dict[str, str] = {}
        for i in range(end_index):
            match = _FIELD_RE.match(lines[i])
            if match is None:
                continue
            key = match.group(1).strip()
            value = match.group(2).strip()
            if key:
                fields[key] = value
        return fields

    def _strip_field_list(self, raw_text: str) -> str:
        lines = raw_text.splitlines()
        start_index, end_index, parsed_any = self._field_list_bounds(lines)
        if not parsed_any:
            return raw_text

        body_start = end_index
        if body_start < len(lines) and not lines[body_start].strip():
            body_start += 1
        preserved_prefix = lines[:start_index]
        return "\n".join(preserved_prefix + lines[body_start:])

    def _field_list_bounds(self, lines: list[str]) -> tuple[int, int, bool]:
        start_index = 0
        while start_index < len(lines) and not lines[start_index].strip():
            start_index += 1

        i = start_index
        parsed_any = False
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                if parsed_any:
                    break
                i += 1
                start_index = i
                continue

            match = _FIELD_RE.match(line)
            if match is None or not match.group(1).strip():
                break
            parsed_any = True
            i += 1

        return start_index, i, parsed_any

    def _extract_title(self, field_list: dict[str, str], body: str, source_uri: str) -> str:
        for key, value in field_list.items():
            if key.strip().lower() == "title" and value.strip():
                return value.strip()

        first_heading = self._extract_first_h1(body)
        if first_heading is not None:
            return first_heading

        source_path = source_uri[5:] if source_uri.startswith("file:") else source_uri
        return PurePosixPath(source_path).stem

    def _extract_first_h1(self, body: str) -> str | None:
        lines = body.splitlines()
        adornment_levels: dict[str, int] = {}
        i = 0
        while i < len(lines):
            heading = self._match_heading(lines, i)
            if heading is None:
                i += 1
                continue

            text, adornment_char, consumed = heading
            if adornment_char not in adornment_levels:
                adornment_levels[adornment_char] = len(adornment_levels) + 1
            if adornment_levels[adornment_char] == 1:
                return text
            i += consumed
        return None

    def _rst_to_markdown(self, body: str) -> str:
        lines = body.splitlines()
        converted: list[str] = []
        adornment_levels: dict[str, int] = {}
        i = 0

        while i < len(lines):
            heading = self._match_heading(lines, i)
            if heading is None:
                converted.append(lines[i])
                i += 1
                continue

            text, adornment_char, consumed = heading
            if adornment_char not in adornment_levels:
                adornment_levels[adornment_char] = len(adornment_levels) + 1
            level = adornment_levels[adornment_char]
            converted.append(f"{'#' * level} {text}")
            i += consumed

        return "\n".join(converted)

    def _match_heading(self, lines: list[str], start_index: int) -> tuple[str, str, int] | None:
        if start_index + 2 < len(lines):
            overline = lines[start_index].strip()
            text_line = lines[start_index + 1].strip()
            underline = lines[start_index + 2].strip()
            if (
                text_line
                and self._is_adornment_line(overline)
                and overline == underline
                and len(overline) >= len(text_line)
            ):
                return text_line, overline[0], 3

        if start_index + 1 < len(lines):
            text_line = lines[start_index].strip()
            underline = lines[start_index + 1].strip()
            if (
                text_line
                and self._is_adornment_line(underline)
                and len(underline) >= len(text_line)
            ):
                return text_line, underline[0], 2

        return None

    def _is_adornment_line(self, line: str) -> bool:
        if not line:
            return False
        char = line[0]
        if char.isalnum():
            return False
        return all(current == char for current in line)
