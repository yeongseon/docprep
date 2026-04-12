from __future__ import annotations

from .models.domain import (
    Chunk,
    ChunkDelta,
    DiffSummary,
    Document,
    IngestResult,
    RevisionDiff,
    Section,
    SectionDelta,
)

_ADDED = "added"
_MODIFIED = "modified"
_REMOVED = "removed"
_UNCHANGED = "unchanged"
_STATUS_ORDER = (_ADDED, _MODIFIED, _REMOVED, _UNCHANGED)


def compute_diff(previous: IngestResult, current: IngestResult) -> RevisionDiff:
    if len(previous.documents) != 1:
        raise ValueError("previous IngestResult must contain exactly one document")
    if len(current.documents) != 1:
        raise ValueError("current IngestResult must contain exactly one document")

    previous_document = previous.documents[0]
    current_document = current.documents[0]
    if previous_document.source_uri != current_document.source_uri:
        raise ValueError("previous and current documents must share source_uri")

    return compute_diff_from_documents(previous_document, current_document)


def compute_diff_from_documents(previous: Document | None, current: Document) -> RevisionDiff:
    if previous is not None and previous.source_uri != current.source_uri:
        raise ValueError("previous and current documents must share source_uri")

    previous_section_hashes = _section_hashes(previous.sections) if previous is not None else {}
    current_section_hashes = _section_hashes(current.sections)
    previous_chunk_hashes = _chunk_hashes(previous.chunks) if previous is not None else {}
    current_chunk_hashes = _chunk_hashes(current.chunks)

    section_deltas = _build_section_deltas(previous_section_hashes, current_section_hashes)
    chunk_deltas = _build_chunk_deltas(previous_chunk_hashes, current_chunk_hashes)

    return RevisionDiff(
        source_uri=current.source_uri,
        previous_revision=previous.source_checksum if previous is not None else "",
        current_revision=current.source_checksum,
        section_deltas=section_deltas,
        chunk_deltas=chunk_deltas,
        summary=_build_summary(section_deltas, chunk_deltas),
    )


def _section_hashes(sections: tuple[Section, ...]) -> dict[str, str]:
    return {section.anchor: section.content_hash for section in sections}


def _chunk_hashes(chunks: tuple[Chunk, ...]) -> dict[str, str]:
    return {chunk.anchor: chunk.content_hash for chunk in chunks}


def _build_section_deltas(
    previous_hashes: dict[str, str],
    current_hashes: dict[str, str],
) -> tuple[SectionDelta, ...]:
    grouped: dict[str, list[SectionDelta]] = {status: [] for status in _STATUS_ORDER}

    for anchor in sorted(current_hashes):
        current_hash = current_hashes[anchor]
        previous_hash = previous_hashes.get(anchor)
        if previous_hash is None:
            status = _ADDED
        elif previous_hash != current_hash:
            status = _MODIFIED
        else:
            status = _UNCHANGED
        grouped[status].append(
            SectionDelta(
                anchor=anchor,
                status=status,
                previous_hash=previous_hash,
                current_hash=current_hash,
            )
        )

    for anchor in sorted(previous_hashes):
        if anchor in current_hashes:
            continue
        grouped[_REMOVED].append(
            SectionDelta(
                anchor=anchor,
                status=_REMOVED,
                previous_hash=previous_hashes[anchor],
                current_hash=None,
            )
        )

    return tuple(delta for status in _STATUS_ORDER for delta in grouped[status])


def _build_chunk_deltas(
    previous_hashes: dict[str, str],
    current_hashes: dict[str, str],
) -> tuple[ChunkDelta, ...]:
    grouped: dict[str, list[ChunkDelta]] = {status: [] for status in _STATUS_ORDER}

    for anchor in sorted(current_hashes):
        current_hash = current_hashes[anchor]
        previous_hash = previous_hashes.get(anchor)
        if previous_hash is None:
            status = _ADDED
        elif previous_hash != current_hash:
            status = _MODIFIED
        else:
            status = _UNCHANGED
        grouped[status].append(
            ChunkDelta(
                anchor=anchor,
                status=status,
                previous_hash=previous_hash,
                current_hash=current_hash,
            )
        )

    for anchor in sorted(previous_hashes):
        if anchor in current_hashes:
            continue
        grouped[_REMOVED].append(
            ChunkDelta(
                anchor=anchor,
                status=_REMOVED,
                previous_hash=previous_hashes[anchor],
                current_hash=None,
            )
        )

    return tuple(delta for status in _STATUS_ORDER for delta in grouped[status])


def _build_summary(
    section_deltas: tuple[SectionDelta, ...],
    chunk_deltas: tuple[ChunkDelta, ...],
) -> DiffSummary:
    section_statuses = tuple(delta.status for delta in section_deltas)
    chunk_statuses = tuple(delta.status for delta in chunk_deltas)
    return DiffSummary(
        sections_added=section_statuses.count(_ADDED),
        sections_removed=section_statuses.count(_REMOVED),
        sections_modified=section_statuses.count(_MODIFIED),
        sections_unchanged=section_statuses.count(_UNCHANGED),
        chunks_added=chunk_statuses.count(_ADDED),
        chunks_removed=chunk_statuses.count(_REMOVED),
        chunks_modified=chunk_statuses.count(_MODIFIED),
        chunks_unchanged=chunk_statuses.count(_UNCHANGED),
    )


__all__ = ["compute_diff", "compute_diff_from_documents"]
