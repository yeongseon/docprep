from __future__ import annotations

import json
import time
import uuid

from docprep import compute_diff, compute_diff_from_documents
from docprep.ids import DOCPREP_NAMESPACE
from docprep.models import DiffSummary, RevisionDiff
from docprep.models.domain import Chunk, Document, IngestResult, Section


def _build_document(
    *,
    source_checksum: str,
    section_entries: tuple[tuple[str, str], ...],
    chunk_entries: tuple[tuple[str, str], ...],
    source_uri: str = "file:test.md",
) -> Document:
    doc_id = uuid.uuid5(DOCPREP_NAMESPACE, source_uri)
    section_ids: dict[str, uuid.UUID] = {}
    sections: list[Section] = []
    for order_index, (anchor, content_hash) in enumerate(section_entries):
        section_id = uuid.uuid5(DOCPREP_NAMESPACE, f"{doc_id}:section:{anchor}")
        section_ids[anchor] = section_id
        sections.append(
            Section(
                id=section_id,
                document_id=doc_id,
                order_index=order_index,
                heading=anchor,
                heading_level=1,
                anchor=anchor,
                content_hash=content_hash,
            )
        )

    chunks: list[Chunk] = []
    for order_index, (anchor, content_hash) in enumerate(chunk_entries):
        section_anchor = anchor.split(":", 1)[0]
        chunk_section_id = section_ids.get(section_anchor)
        if chunk_section_id is None:
            chunk_section_id = uuid.uuid5(DOCPREP_NAMESPACE, f"{doc_id}:section:{section_anchor}")
        chunks.append(
            Chunk(
                id=uuid.uuid5(DOCPREP_NAMESPACE, f"{doc_id}:chunk:{anchor}"),
                document_id=doc_id,
                section_id=chunk_section_id,
                order_index=order_index,
                section_chunk_index=0,
                anchor=anchor,
                content_hash=content_hash,
                content_text=f"body {anchor}",
            )
        )

    return Document(
        id=doc_id,
        source_uri=source_uri,
        title="Test",
        source_checksum=source_checksum,
        sections=tuple(sections),
        chunks=tuple(chunks),
    )


def test_first_ingestion_marks_all_added() -> None:
    current = _build_document(
        source_checksum="rev-1",
        section_entries=(("intro", "s1"), ("usage", "s2")),
        chunk_entries=(("intro:c1", "c1"), ("usage:c2", "c2")),
    )

    diff = compute_diff_from_documents(None, current)

    assert isinstance(diff, RevisionDiff)
    assert diff.previous_revision == ""
    assert tuple(delta.status for delta in diff.section_deltas) == ("added", "added")
    assert tuple(delta.status for delta in diff.chunk_deltas) == ("added", "added")
    assert diff.summary == DiffSummary(sections_added=2, chunks_added=2)


def test_identical_reingestion_marks_all_unchanged() -> None:
    previous = _build_document(
        source_checksum="rev-1",
        section_entries=(("intro", "s1"), ("usage", "s2")),
        chunk_entries=(("intro:c1", "c1"), ("usage:c2", "c2")),
    )
    current = _build_document(
        source_checksum="rev-1",
        section_entries=(("intro", "s1"), ("usage", "s2")),
        chunk_entries=(("intro:c1", "c1"), ("usage:c2", "c2")),
    )

    diff = compute_diff_from_documents(previous, current)

    assert tuple(delta.status for delta in diff.section_deltas) == ("unchanged", "unchanged")
    assert tuple(delta.status for delta in diff.chunk_deltas) == ("unchanged", "unchanged")
    assert diff.summary == DiffSummary(sections_unchanged=2, chunks_unchanged=2)


def test_modified_content_marks_matching_anchors_modified() -> None:
    previous = _build_document(
        source_checksum="rev-1",
        section_entries=(("intro", "s1"),),
        chunk_entries=(("intro:c1", "c1"),),
    )
    current = _build_document(
        source_checksum="rev-2",
        section_entries=(("intro", "s1-new"),),
        chunk_entries=(("intro:c1", "c1-new"),),
    )

    diff = compute_diff_from_documents(previous, current)

    assert tuple(delta.status for delta in diff.section_deltas) == ("modified",)
    assert tuple(delta.status for delta in diff.chunk_deltas) == ("modified",)
    assert diff.summary == DiffSummary(sections_modified=1, chunks_modified=1)


def test_section_added_is_reported() -> None:
    previous = _build_document(
        source_checksum="rev-1",
        section_entries=(("intro", "s1"),),
        chunk_entries=(("intro:c1", "c1"),),
    )
    current = _build_document(
        source_checksum="rev-2",
        section_entries=(("intro", "s1"), ("usage", "s2")),
        chunk_entries=(("intro:c1", "c1"), ("usage:c2", "c2")),
    )

    diff = compute_diff_from_documents(previous, current)

    assert tuple(delta.anchor for delta in diff.section_deltas) == ("usage", "intro")
    assert tuple(delta.status for delta in diff.section_deltas) == ("added", "unchanged")
    assert tuple(delta.anchor for delta in diff.chunk_deltas) == ("usage:c2", "intro:c1")
    assert tuple(delta.status for delta in diff.chunk_deltas) == ("added", "unchanged")


def test_section_removed_is_reported() -> None:
    previous = _build_document(
        source_checksum="rev-1",
        section_entries=(("intro", "s1"), ("usage", "s2")),
        chunk_entries=(("intro:c1", "c1"), ("usage:c2", "c2")),
    )
    current = _build_document(
        source_checksum="rev-2",
        section_entries=(("intro", "s1"),),
        chunk_entries=(("intro:c1", "c1"),),
    )

    diff = compute_diff_from_documents(previous, current)

    assert tuple(delta.anchor for delta in diff.section_deltas) == ("usage", "intro")
    assert tuple(delta.status for delta in diff.section_deltas) == ("removed", "unchanged")
    assert tuple(delta.anchor for delta in diff.chunk_deltas) == ("usage:c2", "intro:c1")
    assert tuple(delta.status for delta in diff.chunk_deltas) == ("removed", "unchanged")


def test_mixed_changes_follow_status_ordering() -> None:
    previous = _build_document(
        source_checksum="rev-1",
        section_entries=(("a", "sa"), ("b", "sb"), ("c", "sc")),
        chunk_entries=(("a:ca", "ca"), ("b:cb", "cb"), ("c:cc", "cc")),
    )
    current = _build_document(
        source_checksum="rev-2",
        section_entries=(("b", "sb-new"), ("c", "sc"), ("d", "sd")),
        chunk_entries=(("b:cb", "cb-new"), ("c:cc", "cc"), ("d:cd", "cd")),
    )

    diff = compute_diff_from_documents(previous, current)

    assert tuple(delta.anchor for delta in diff.section_deltas) == ("d", "b", "a", "c")
    assert tuple(delta.status for delta in diff.section_deltas) == (
        "added",
        "modified",
        "removed",
        "unchanged",
    )
    assert tuple(delta.anchor for delta in diff.chunk_deltas) == ("d:cd", "b:cb", "a:ca", "c:cc")
    assert tuple(delta.status for delta in diff.chunk_deltas) == (
        "added",
        "modified",
        "removed",
        "unchanged",
    )
    assert diff.summary == DiffSummary(
        sections_added=1,
        sections_removed=1,
        sections_modified=1,
        sections_unchanged=1,
        chunks_added=1,
        chunks_removed=1,
        chunks_modified=1,
        chunks_unchanged=1,
    )


def test_reordered_sections_with_same_content_are_unchanged() -> None:
    previous = _build_document(
        source_checksum="rev-1",
        section_entries=(("intro", "s1"), ("usage", "s2")),
        chunk_entries=(("intro:c1", "c1"), ("usage:c2", "c2")),
    )
    current = _build_document(
        source_checksum="rev-2",
        section_entries=(("usage", "s2"), ("intro", "s1")),
        chunk_entries=(("usage:c2", "c2"), ("intro:c1", "c1")),
    )

    diff = compute_diff_from_documents(previous, current)

    assert tuple(delta.status for delta in diff.section_deltas) == ("unchanged", "unchanged")
    assert tuple(delta.status for delta in diff.chunk_deltas) == ("unchanged", "unchanged")
    assert diff.summary == DiffSummary(sections_unchanged=2, chunks_unchanged=2)


def test_empty_document_produces_empty_deltas() -> None:
    current = _build_document(source_checksum="rev-empty", section_entries=(), chunk_entries=())

    diff = compute_diff_from_documents(None, current)

    assert diff.section_deltas == ()
    assert diff.chunk_deltas == ()
    assert diff.summary == DiffSummary()


def test_revision_diff_to_dict_is_json_serializable() -> None:
    current = _build_document(
        source_checksum="rev-1",
        section_entries=(("intro", "s1"),),
        chunk_entries=(("intro:c1", "c1"),),
    )

    diff = compute_diff_from_documents(None, current)
    payload = diff.to_dict()

    assert payload["source_uri"] == "file:test.md"
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    assert decoded["summary"]["sections_added"] == 1
    assert decoded["summary"]["chunks_added"] == 1


def test_diff_performance_for_500_sections_under_100ms() -> None:
    section_entries = tuple((f"s-{idx}", f"hs-{idx}") for idx in range(500))
    chunk_entries = tuple((f"s-{idx}:c-{idx}", f"hc-{idx}") for idx in range(500))
    previous = _build_document(
        source_checksum="rev-1",
        section_entries=section_entries,
        chunk_entries=chunk_entries,
    )
    current = _build_document(
        source_checksum="rev-2",
        section_entries=section_entries,
        chunk_entries=chunk_entries,
    )

    start = time.perf_counter()
    diff = compute_diff_from_documents(previous, current)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert diff.summary == DiffSummary(sections_unchanged=500, chunks_unchanged=500)
    assert elapsed_ms < 100


def test_compute_diff_wrapper_accepts_ingest_results() -> None:
    previous_document = _build_document(
        source_checksum="rev-1",
        section_entries=(("intro", "s1"),),
        chunk_entries=(("intro:c1", "c1"),),
    )
    current_document = _build_document(
        source_checksum="rev-2",
        section_entries=(("intro", "s1-new"), ("usage", "s2")),
        chunk_entries=(("intro:c1", "c1-new"), ("usage:c2", "c2")),
    )
    previous = IngestResult(documents=(previous_document,))
    current = IngestResult(documents=(current_document,))

    diff = compute_diff(previous, current)

    assert diff.previous_revision == "rev-1"
    assert diff.current_revision == "rev-2"
    assert diff.source_uri == "file:test.md"
    assert diff.summary == DiffSummary(
        sections_added=1,
        sections_modified=1,
        chunks_added=1,
        chunks_modified=1,
    )
