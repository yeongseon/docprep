from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import create_engine

from docprep.ids import (
    chunk_anchor,
    chunk_id,
    content_hash,
    document_id,
    section_anchor,
    section_id,
    sha256_checksum,
)
from docprep.models.domain import Chunk, DeletePolicy, Document, Section, SourceScope
from docprep.sinks.sqlalchemy import SQLAlchemySink


def _make_doc(
    uri: str = "file:test.md",
    *,
    title: str = "Test",
    section_bodies: Sequence[str] = ("Hello",),
    chunks_per_section: Sequence[int] | None = None,
) -> Document:
    doc_id_val = document_id(uri)
    sibling_counts: dict[tuple[str, str], int] = {}
    dup_counts: dict[tuple[str, str], int] = {}

    section_counts = tuple(chunks_per_section or [1] * len(section_bodies))
    section_rows: list[Section] = []
    chunk_rows: list[Chunk] = []

    for section_index, section_body in enumerate(section_bodies):
        heading = "Intro" if section_index == 0 else f"Section {section_index + 1}"
        s_anchor = section_anchor(heading, "__root__", sibling_counts)
        s_hash = content_hash(section_body)
        s_id = section_id(doc_id_val, s_anchor)

        section_rows.append(
            Section(
                id=s_id,
                document_id=doc_id_val,
                order_index=section_index,
                heading=heading,
                heading_level=1,
                anchor=s_anchor,
                content_hash=s_hash,
                content_markdown=section_body,
            )
        )

        chunk_count = section_counts[section_index]
        for chunk_index in range(chunk_count):
            chunk_text = section_body if chunk_count == 1 else f"{section_body} [{chunk_index}]"
            c_hash = content_hash(chunk_text)
            c_anchor_str = chunk_anchor(s_anchor, c_hash, dup_counts)
            c_id = chunk_id(doc_id_val, c_anchor_str)
            chunk_rows.append(
                Chunk(
                    id=c_id,
                    document_id=doc_id_val,
                    section_id=s_id,
                    order_index=len(chunk_rows),
                    section_chunk_index=chunk_index,
                    anchor=c_anchor_str,
                    content_hash=c_hash,
                    content_text=chunk_text,
                )
            )

    body = "\n\n".join(section_bodies)
    return Document(
        id=doc_id_val,
        source_uri=uri,
        title=title,
        source_checksum=sha256_checksum(body),
        body_markdown=body,
        sections=tuple(section_rows),
        chunks=tuple(chunk_rows),
    )


def test_delete_by_uri_deletes_document_and_children() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    doc = _make_doc(uri="file:docs/a.md")
    _ = sink.upsert([doc])

    result = sink.delete_by_uri(doc.source_uri)

    assert result.deleted_source_uris == (doc.source_uri,)
    assert result.deleted_document_count == 1
    assert result.deleted_section_count == 1
    assert result.deleted_chunk_count == 1
    assert sink.get_document(doc.source_uri) is None
    assert sink.stats().documents == 0


def test_delete_by_uri_deletes_revision_history() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    doc_v1 = _make_doc(uri="file:docs/revisions.md", section_bodies=("Version one",))
    doc_v2 = _make_doc(uri="file:docs/revisions.md", section_bodies=("Version two",))

    _ = sink.upsert([doc_v1])
    _ = sink.upsert([doc_v2])

    revisions_before = sink.get_revisions(doc_v1.id)
    assert len(revisions_before) == 2

    result = sink.delete_by_uri(doc_v1.source_uri)

    assert sink.get_revisions(doc_v1.id) == []
    assert result.deleted_revision_count > 0
    assert result.deleted_revision_count == len(revisions_before)


def test_delete_by_uri_not_found_returns_empty_result() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))

    result = sink.delete_by_uri("file:docs/missing.md")

    assert result.deleted_source_uris == ()
    assert result.deleted_document_count == 0
    assert result.deleted_section_count == 0
    assert result.deleted_chunk_count == 0


def test_delete_by_uri_dry_run_returns_counts_without_deleting() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    doc = _make_doc(uri="file:docs/a.md")
    _ = sink.upsert([doc])

    result = sink.delete_by_uri(doc.source_uri, dry_run=True)

    assert result.deleted_source_uris == (doc.source_uri,)
    assert result.deleted_document_count == 1
    assert result.deleted_section_count == 1
    assert result.deleted_chunk_count == 1
    assert result.dry_run is True
    assert sink.get_document(doc.source_uri) is not None
    assert sink.stats().documents == 1


def test_delete_by_prefix_deletes_all_matching_documents() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    doc_a = _make_doc(uri="file:docs/a.md")
    doc_b = _make_doc(uri="file:docs/b.md")
    doc_keep = _make_doc(uri="file:notes/c.md")
    _ = sink.upsert([doc_a, doc_b, doc_keep])

    result = sink.delete_by_prefix("file:docs/")

    assert result.deleted_source_uris == ("file:docs/a.md", "file:docs/b.md")
    assert result.deleted_document_count == 2
    assert result.deleted_section_count == 2
    assert result.deleted_chunk_count == 2
    assert sink.get_document("file:docs/a.md") is None
    assert sink.get_document("file:docs/b.md") is None
    assert sink.get_document("file:notes/c.md") is not None


def test_delete_by_prefix_partial_prefix_match_works() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    doc_nested = _make_doc(uri="file:docs/guides/a.md")
    doc_other = _make_doc(uri="file:reference/a.md")
    _ = sink.upsert([doc_nested, doc_other])

    result = sink.delete_by_prefix("file:docs/")

    assert result.deleted_source_uris == ("file:docs/guides/a.md",)
    assert sink.get_document("file:docs/guides/a.md") is None
    assert sink.get_document("file:reference/a.md") is not None


def test_delete_by_prefix_dry_run_counts_without_deletion() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    doc_a = _make_doc(uri="file:docs/a.md")
    doc_b = _make_doc(uri="file:docs/b.md")
    _ = sink.upsert([doc_a, doc_b])

    result = sink.delete_by_prefix("file:docs/", dry_run=True)

    assert result.deleted_document_count == 2
    assert result.deleted_section_count == 2
    assert result.deleted_chunk_count == 2
    assert result.dry_run is True
    assert sink.stats().documents == 2


def test_delete_by_uris_batch_delete_multiple() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    doc_a = _make_doc(uri="file:docs/a.md")
    doc_b = _make_doc(uri="file:docs/b.md")
    doc_c = _make_doc(uri="file:docs/c.md")
    _ = sink.upsert([doc_a, doc_b, doc_c])

    result = sink.delete_by_uris([doc_a.source_uri, doc_c.source_uri])

    assert result.deleted_source_uris == (doc_a.source_uri, doc_c.source_uri)
    assert result.deleted_document_count == 2
    assert sink.get_document(doc_a.source_uri) is None
    assert sink.get_document(doc_b.source_uri) is not None
    assert sink.get_document(doc_c.source_uri) is None


def test_delete_by_uris_mixed_found_and_not_found() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    doc_a = _make_doc(uri="file:docs/a.md")
    doc_b = _make_doc(uri="file:docs/b.md")
    _ = sink.upsert([doc_a, doc_b])

    result = sink.delete_by_uris([doc_b.source_uri, "file:docs/missing.md", doc_a.source_uri])

    assert result.deleted_source_uris == (doc_b.source_uri, doc_a.source_uri)
    assert result.deleted_document_count == 2
    assert result.deleted_section_count == 2
    assert result.deleted_chunk_count == 2


def test_sync_hard_delete_upserts_and_deletes_stale() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    keep = _make_doc(uri="file:docs/keep.md")
    stale = _make_doc(uri="file:docs/stale.md")
    _ = sink.upsert([keep, stale])

    current_keep = _make_doc(uri="file:docs/keep.md")
    new_doc = _make_doc(uri="file:docs/new.md")
    result = sink.sync(
        [current_keep, new_doc],
        scope=SourceScope(prefixes=("file:docs/",)),
        delete_policy=DeletePolicy.HARD_DELETE,
    )

    assert result.upsert_result.skipped_source_uris == ("file:docs/keep.md",)
    assert result.upsert_result.updated_source_uris == ("file:docs/new.md",)
    assert result.upsert_result.deleted_source_uris == ("file:docs/stale.md",)
    assert result.delete_result.deleted_source_uris == ("file:docs/stale.md",)
    assert sink.get_document("file:docs/stale.md") is None


def test_delete_policy_has_only_hard_delete_and_ignore() -> None:
    assert tuple(DeletePolicy) == (DeletePolicy.HARD_DELETE, DeletePolicy.IGNORE)


def test_sync_ignore_upserts_without_deleting_stale() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    stale = _make_doc(uri="file:docs/stale.md")
    _ = sink.upsert([stale])

    result = sink.sync(
        [_make_doc(uri="file:docs/new.md")],
        scope=SourceScope(prefixes=("file:docs/",)),
        delete_policy=DeletePolicy.IGNORE,
    )

    assert result.upsert_result.updated_source_uris == ("file:docs/new.md",)
    assert result.delete_result.deleted_source_uris == ()
    assert sink.get_document("file:docs/stale.md") is not None


def test_sync_dry_run_computes_without_changes() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    keep = _make_doc(uri="file:docs/keep.md")
    stale = _make_doc(uri="file:docs/stale.md")
    _ = sink.upsert([keep, stale])

    result = sink.sync(
        [
            _make_doc(uri="file:docs/keep.md"),
            _make_doc(uri="file:docs/new.md"),
        ],
        scope=SourceScope(prefixes=("file:docs/",)),
        delete_policy=DeletePolicy.HARD_DELETE,
        dry_run=True,
    )

    assert result.upsert_result.skipped_source_uris == ("file:docs/keep.md",)
    assert result.upsert_result.updated_source_uris == ("file:docs/new.md",)
    assert result.upsert_result.deleted_source_uris == ("file:docs/stale.md",)
    assert result.delete_result.deleted_document_count == 1
    assert result.delete_result.dry_run is True
    assert sink.get_document("file:docs/stale.md") is not None
    assert sink.get_document("file:docs/new.md") is None


def test_sync_with_no_stale_deletes_nothing() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    doc_a = _make_doc(uri="file:docs/a.md")
    doc_b = _make_doc(uri="file:docs/b.md")
    _ = sink.upsert([doc_a, doc_b])

    result = sink.sync(
        [
            _make_doc(uri="file:docs/a.md"),
            _make_doc(uri="file:docs/b.md"),
        ],
        scope=SourceScope(prefixes=("file:docs/",)),
        delete_policy=DeletePolicy.HARD_DELETE,
    )

    assert result.delete_result.deleted_source_uris == ()
    assert result.delete_result.deleted_document_count == 0


def test_sync_scope_limited_deletes_only_within_scope() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    stale_in_scope = _make_doc(uri="file:docs/api/old.md")
    keep_outside_scope = _make_doc(uri="file:docs/reference/keep.md")
    _ = sink.upsert([stale_in_scope, keep_outside_scope])

    result = sink.sync(
        [_make_doc(uri="file:docs/api/new.md")],
        scope=SourceScope(prefixes=("file:docs/api/",)),
        delete_policy=DeletePolicy.HARD_DELETE,
    )

    assert result.delete_result.deleted_source_uris == ("file:docs/api/old.md",)
    assert sink.get_document("file:docs/api/old.md") is None
    assert sink.get_document("file:docs/reference/keep.md") is not None


def test_delete_counts_are_accurate_for_sections_and_chunks() -> None:
    sink = SQLAlchemySink(engine=create_engine("sqlite://"))
    doc = _make_doc(
        uri="file:docs/complex.md",
        section_bodies=("A", "B"),
        chunks_per_section=(1, 2),
    )
    _ = sink.upsert([doc])

    result = sink.delete_by_uri(doc.source_uri)

    assert result.deleted_document_count == 1
    assert result.deleted_section_count == 2
    assert result.deleted_chunk_count == 3
    stats = sink.stats()
    assert stats.documents == 0
    assert stats.sections == 0
    assert stats.chunks == 0
