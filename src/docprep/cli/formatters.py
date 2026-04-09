"""Output formatters for the CLI."""

from __future__ import annotations

import json
from typing import Any

from docprep.models.domain import Document, IngestResult


def format_ingest_result(result: IngestResult, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(_ingest_result_to_dict(result), indent=2)

    lines: list[str] = []
    lines.append(f"Ingested {len(result.documents)} document(s)")
    if result.skipped_source_uris:
        lines.append(f"Skipped (unchanged): {len(result.skipped_source_uris)}")
    if result.persisted:
        lines.append(f"Persisted via: {result.sink_name}")
    return "\n".join(lines)


def format_preview(documents: tuple[Document, ...], *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps([_document_preview_dict(d) for d in documents], indent=2)

    lines: list[str] = []
    for doc in documents:
        lines.append(f"Document: {doc.title}")
        lines.append(f"  Source: {doc.source_uri}")
        lines.append(f"  Checksum: {doc.source_checksum[:12]}...")
        lines.append(f"  Sections: {len(doc.sections)}")
        lines.append(f"  Chunks: {len(doc.chunks)}")
        for section in doc.sections:
            prefix = "  " * (section.heading_level + 1)
            heading_display = section.heading or "(root)"
            lines.append(f"{prefix}[{section.heading_level}] {heading_display}")
        lines.append("")
    return "\n".join(lines)


def format_stats(stats: dict[str, int], *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(stats, indent=2)

    lines: list[str] = []
    for key, value in stats.items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def _ingest_result_to_dict(result: IngestResult) -> dict[str, Any]:
    return {
        "documents_count": len(result.documents),
        "skipped_source_uris": list(result.skipped_source_uris),
        "persisted": result.persisted,
        "sink_name": result.sink_name,
    }


def _document_preview_dict(doc: Document) -> dict[str, Any]:
    return {
        "id": str(doc.id),
        "title": doc.title,
        "source_uri": doc.source_uri,
        "source_checksum": doc.source_checksum,
        "sections_count": len(doc.sections),
        "chunks_count": len(doc.chunks),
        "sections": [
            {
                "heading": s.heading,
                "heading_level": s.heading_level,
                "heading_path": list(s.heading_path),
            }
            for s in doc.sections
        ],
    }
