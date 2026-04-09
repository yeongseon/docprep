"""Markdown parser — converts loaded Markdown sources into Documents."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath

import frontmatter

from docprep.exceptions import ParseError
from docprep.ids import document_id
from docprep.loaders.types import LoadedSource
from docprep.metadata import normalize_metadata
from docprep.models.domain import Document


class MarkdownParser:
    """Parses a loaded Markdown source into a Document without sections or chunks."""

    def parse(self, loaded_source: LoadedSource) -> Document:
        try:
            post = frontmatter.loads(loaded_source.raw_text)
        except Exception as exc:
            raise ParseError(
                f"Failed to parse frontmatter from {loaded_source.source_uri}: {exc}"
            ) from exc

        fm_raw: dict[str, object] = dict(post.metadata)
        body = post.content

        normalized_fm = normalize_metadata(
            fm_raw,
            source=loaded_source.source_uri,
            field_name="frontmatter",
        )
        normalized_source_meta = normalize_metadata(
            loaded_source.source_metadata,
            source=loaded_source.source_uri,
            field_name="source_metadata",
        )

        title = self._extract_title(normalized_fm, body, loaded_source.source_uri)
        doc_id = document_id(loaded_source.source_uri)

        return Document(
            id=doc_id,
            source_uri=loaded_source.source_uri,
            title=title,
            source_checksum=loaded_source.checksum,
            source_type="markdown",
            frontmatter=normalized_fm,
            source_metadata=normalized_source_meta,
            body_markdown=body,
        )

    def _extract_title(
        self,
        fm: Mapping[str, object],
        body: str,
        source_uri: str,
    ) -> str:
        # 1) frontmatter["title"]
        fm_title = fm.get("title")
        if isinstance(fm_title, str) and fm_title.strip():
            return fm_title.strip()

        # 2) first H1 heading in body
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("##"):
                return stripped[2:].strip()

        # 3) stem of the source path
        return PurePosixPath(source_uri).stem
