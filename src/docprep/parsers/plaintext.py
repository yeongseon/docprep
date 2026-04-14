from __future__ import annotations

from pathlib import PurePosixPath

from ..ids import document_id
from ..loaders.types import LoadedSource
from ..metadata import normalize_metadata
from ..models.domain import Document


class PlainTextParser:
    def parse(self, loaded_source: LoadedSource) -> Document:
        title = self._extract_title(loaded_source.raw_text, loaded_source.source_uri)
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
            source_type="plaintext",
            frontmatter={},
            source_metadata=normalized_source_meta,
            body_markdown=loaded_source.raw_text,
        )

    def _extract_title(self, raw_text: str, source_uri: str) -> str:
        for line in raw_text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped
        source_path = source_uri[5:] if source_uri.startswith("file:") else source_uri
        return PurePosixPath(source_path).stem
