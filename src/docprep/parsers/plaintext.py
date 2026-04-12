from __future__ import annotations

from pathlib import PurePosixPath

from ..ids import document_id
from ..loaders.types import LoadedSource
from ..models.domain import Document


class PlainTextParser:
    def parse(self, loaded_source: LoadedSource) -> Document:
        title = self._extract_title(loaded_source.raw_text, loaded_source.source_uri)
        return Document(
            id=document_id(loaded_source.source_uri),
            source_uri=loaded_source.source_uri,
            title=title,
            source_checksum=loaded_source.checksum,
            source_type="plaintext",
            frontmatter={},
            source_metadata={},
            body_markdown=loaded_source.raw_text,
        )

    def _extract_title(self, raw_text: str, source_uri: str) -> str:
        for line in raw_text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
        source_path = source_uri[5:] if source_uri.startswith("file:") else source_uri
        return PurePosixPath(source_path).stem
