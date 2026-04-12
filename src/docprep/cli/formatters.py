"""Output formatters for the CLI."""

from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from docprep.models.domain import Chunk, DeleteResult, Document, IngestResult, RevisionDiff, Section


def format_ingest_result(result: IngestResult, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(_ingest_result_to_dict(result), indent=2)

    lines: list[str] = []
    lines.append(f"Ingested {len(result.documents)} document(s)")
    lines.append(f"  Processed: {result.processed_count}")
    if result.updated_count:
        lines.append(f"  Updated: {result.updated_count}")
    if result.skipped_count:
        lines.append(f"  Skipped (unchanged): {result.skipped_count}")
    if result.failed_count:
        lines.append(f"  Failed: {result.failed_count}")
    if result.deleted_count:
        lines.append(f"  Deleted: {result.deleted_count}")
    if result.persisted:
        lines.append(f"Persisted via: {result.sink_name}")
    if result.stage_reports:
        lines.append("Stage timings:")
        for report in result.stage_reports:
            lines.append(f"  {report.stage}: {report.elapsed_ms:.1f}ms")
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


def format_diff(diffs: list[RevisionDiff], *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps([diff.to_dict() for diff in diffs], indent=2)

    if not diffs:
        return "No documents to diff."

    lines: list[str] = []
    changed_count = 0
    for diff in diffs:
        summary = diff.summary
        has_changes = (
            summary.sections_added
            + summary.sections_removed
            + summary.sections_modified
            + summary.chunks_added
            + summary.chunks_removed
            + summary.chunks_modified
            > 0
        )
        if has_changes:
            changed_count += 1

        source_display = diff.source_uri
        if not diff.previous_revision:
            source_display = f"{source_display} (new)"

        lines.append(source_display)
        lines.append(
            "  sections: "
            f"{summary.sections_added} added, "
            f"{summary.sections_removed} removed, "
            f"{summary.sections_modified} modified, "
            f"{summary.sections_unchanged} unchanged"
        )
        lines.append(
            "  chunks: "
            f"{summary.chunks_added} added, "
            f"{summary.chunks_removed} removed, "
            f"{summary.chunks_modified} modified, "
            f"{summary.chunks_unchanged} unchanged"
        )
        lines.append("")

    unchanged_count = len(diffs) - changed_count
    lines.append(f"Summary: {changed_count} documents changed, {unchanged_count} unchanged")
    return "\n".join(lines)


def format_inspect_document(doc: Document, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(_document_inspect_dict(doc), indent=2)

    lines: list[str] = []
    lines.append(f"Document: {doc.title}")
    lines.append(f"  URI: {doc.source_uri}")
    lines.append(f"  Checksum: {doc.source_checksum}")
    lines.append(f"  Sections: {len(doc.sections)}")
    lines.append(f"  Chunks: {len(doc.chunks)}")
    if doc.sections:
        lines.append("")
        lines.append("  Sections:")
        for index, section in enumerate(doc.sections, start=1):
            heading_display = section.heading or "(root)"
            lines.append(
                f"    [{index}] {heading_display} "
                f"(anchor: {section.anchor}, hash: {section.content_hash})"
            )
    return "\n".join(lines)


def format_inspect_section(section: Section, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(_section_inspect_dict(section), indent=2)

    lines: list[str] = []
    lines.append(f"Section: {section.heading or '(root)'}")
    lines.append(f"  Anchor: {section.anchor}")
    lines.append(f"  Level: {section.heading_level}")
    lines.append(f"  Hash: {section.content_hash}")
    lines.append(f"  Document ID: {section.document_id}")
    return "\n".join(lines)


def format_inspect_chunk(chunk: Chunk, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(_chunk_inspect_dict(chunk), indent=2)

    preview = chunk.content_text.replace("\n", " ").strip()
    if len(preview) > 80:
        preview = f"{preview[:77]}..."
    section_anchor = chunk.anchor.split(":", 1)[0] if chunk.anchor else ""

    lines: list[str] = []
    lines.append(f"Chunk: {chunk.anchor}")
    lines.append(f"  Anchor: {chunk.anchor}")
    lines.append(f"  Hash: {chunk.content_hash}")
    lines.append(f"  Section: {section_anchor}")
    lines.append(f"  Chars: {chunk.char_start}-{chunk.char_end}")
    lines.append(f'  Text preview: "{preview}"')
    return "\n".join(lines)


def format_delete_result(result: DeleteResult, *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(_delete_result_dict(result), indent=2)

    prefix = "[DRY RUN] Would delete" if result.dry_run else "Deleted"
    if result.deleted_document_count == 0:
        return f"{prefix} 0 document(s)."

    if result.deleted_document_count == 1 and result.deleted_source_uris:
        return (
            f"{prefix} 1 document: {result.deleted_source_uris[0]} "
            f"({result.deleted_section_count} sections, {result.deleted_chunk_count} chunks)"
        )

    lines: list[str] = []
    lines.append(
        f"{prefix} {result.deleted_document_count} document(s) "
        f"({result.deleted_section_count} sections, {result.deleted_chunk_count} chunks):"
    )
    for source_uri in result.deleted_source_uris:
        lines.append(f"  {source_uri}")
    return "\n".join(lines)


def format_export_summary(
    *,
    records_written: int,
    deleted_written: int = 0,
    changed_only: bool = False,
    as_json: bool = False,
) -> str:
    if as_json:
        return json.dumps(
            {
                "records_written": records_written,
                "deleted_written": deleted_written,
                "changed_only": changed_only,
            },
            indent=2,
        )

    if changed_only:
        return (
            "Exported "
            f"{records_written} changed record(s) and {deleted_written} deleted ID marker(s)."
        )
    return f"Exported {records_written} record(s)."


def _ingest_result_to_dict(result: IngestResult) -> dict[str, Any]:
    data: dict[str, Any] = {
        "documents_count": len(result.documents),
        "processed_count": result.processed_count,
        "updated_count": result.updated_count,
        "skipped_count": result.skipped_count,
        "failed_count": result.failed_count,
        "deleted_count": result.deleted_count,
        "skipped_source_uris": list(result.skipped_source_uris),
        "updated_source_uris": list(result.updated_source_uris),
        "failed_source_uris": list(result.failed_source_uris),
        "deleted_source_uris": list(result.deleted_source_uris),
        "persisted": result.persisted,
        "sink_name": result.sink_name,
    }
    if result.stage_reports:
        data["stage_reports"] = [
            {
                "stage": r.stage,
                "elapsed_ms": round(r.elapsed_ms, 2),
                "input_count": r.input_count,
                "output_count": r.output_count,
                "failed_count": r.failed_count,
            }
            for r in result.stage_reports
        ]
    return data


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


def _document_inspect_dict(doc: Document) -> dict[str, Any]:
    return {
        "id": str(doc.id),
        "source_uri": doc.source_uri,
        "title": doc.title,
        "source_checksum": doc.source_checksum,
        "source_type": doc.source_type,
        "frontmatter": doc.frontmatter,
        "source_metadata": doc.source_metadata,
        "body_markdown": doc.body_markdown,
        "sections": [_section_inspect_dict(section) for section in doc.sections],
        "chunks": [_chunk_inspect_dict(chunk) for chunk in doc.chunks],
    }


def _section_inspect_dict(section: Section) -> dict[str, Any]:
    return {
        "id": str(section.id),
        "document_id": str(section.document_id),
        "order_index": section.order_index,
        "parent_id": str(section.parent_id) if section.parent_id is not None else None,
        "heading": section.heading,
        "heading_level": section.heading_level,
        "anchor": section.anchor,
        "content_hash": section.content_hash,
        "heading_path": list(section.heading_path),
        "lineage": list(section.lineage),
        "content_markdown": section.content_markdown,
    }


def _chunk_inspect_dict(chunk: Chunk) -> dict[str, Any]:
    return {
        "id": str(chunk.id),
        "document_id": str(chunk.document_id),
        "section_id": str(chunk.section_id),
        "order_index": chunk.order_index,
        "section_chunk_index": chunk.section_chunk_index,
        "anchor": chunk.anchor,
        "content_hash": chunk.content_hash,
        "content_text": chunk.content_text,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "token_count": chunk.token_count,
        "heading_path": list(chunk.heading_path),
        "lineage": list(chunk.lineage),
    }


def _delete_result_dict(result: DeleteResult) -> dict[str, Any]:
    data = asdict(result)
    data["deleted_source_uris"] = list(result.deleted_source_uris)
    return data
