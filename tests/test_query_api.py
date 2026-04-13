from __future__ import annotations

from typing import cast
import uuid

from sqlalchemy import Engine, create_engine

from docprep.ids import (
    chunk_anchor,
    chunk_id,
    content_hash,
    document_id,
    section_anchor,
    section_id,
    sha256_checksum,
)
from docprep.models.domain import Chunk, Document, Page, Section
from docprep.sinks.sqlalchemy import SQLAlchemySink


def _make_engine() -> Engine:
    return create_engine("sqlite:///:memory:")


def _make_doc(
    source_uri: str = "file:test.md", title: str = "Test", body: str = "Hello"
) -> Document:
    doc_id = document_id(source_uri)
    sibling_counts: dict[tuple[str, str], int] = {}
    s_anchor = section_anchor("Intro", "__root__", sibling_counts)
    s_hash = content_hash(body)
    s_id = section_id(doc_id, s_anchor)
    c_hash = content_hash(body)
    c_anchor_str = chunk_anchor(s_anchor, 0)
    c_id = chunk_id(doc_id, c_anchor_str)
    return Document(
        id=doc_id,
        source_uri=source_uri,
        title=title,
        source_checksum=sha256_checksum(body),
        body_markdown=body,
        sections=(
            Section(
                id=s_id,
                document_id=doc_id,
                order_index=0,
                heading="Intro",
                heading_level=1,
                anchor=s_anchor,
                content_hash=s_hash,
                content_markdown=body,
            ),
        ),
        chunks=(
            Chunk(
                id=c_id,
                document_id=doc_id,
                section_id=s_id,
                order_index=0,
                section_chunk_index=0,
                anchor=c_anchor_str,
                content_hash=c_hash,
                content_text=body,
            ),
        ),
    )


def _make_doc_with_multiple_sections_and_chunks(
    source_uri: str = "file:complex.md",
    title: str = "Complex",
) -> Document:
    doc_id = document_id(source_uri)

    intro_anchor = "intro"
    detail_anchor = "details"
    intro_id = section_id(doc_id, intro_anchor)
    detail_id = section_id(doc_id, detail_anchor)

    intro_text_1 = "Intro chunk one"
    intro_text_2 = "Intro chunk two"
    detail_text = "Details chunk"

    intro_chunk_1_anchor = chunk_anchor(intro_anchor, 0)
    intro_chunk_2_anchor = chunk_anchor(intro_anchor, 1)
    detail_chunk_anchor = chunk_anchor(detail_anchor, 0)

    body = f"{intro_text_1}\n{intro_text_2}\n{detail_text}"
    return Document(
        id=doc_id,
        source_uri=source_uri,
        title=title,
        source_checksum=sha256_checksum(body),
        body_markdown=body,
        sections=(
            Section(
                id=intro_id,
                document_id=doc_id,
                order_index=0,
                heading="Intro",
                heading_level=1,
                anchor=intro_anchor,
                content_hash=content_hash(f"{intro_text_1}\n{intro_text_2}"),
                content_markdown=f"{intro_text_1}\n{intro_text_2}",
            ),
            Section(
                id=detail_id,
                document_id=doc_id,
                order_index=1,
                heading="Details",
                heading_level=2,
                anchor=detail_anchor,
                content_hash=content_hash(detail_text),
                content_markdown=detail_text,
            ),
        ),
        chunks=(
            Chunk(
                id=chunk_id(doc_id, intro_chunk_1_anchor),
                document_id=doc_id,
                section_id=intro_id,
                order_index=0,
                section_chunk_index=0,
                anchor=intro_chunk_1_anchor,
                content_hash=content_hash(intro_text_1),
                content_text=intro_text_1,
            ),
            Chunk(
                id=chunk_id(doc_id, intro_chunk_2_anchor),
                document_id=doc_id,
                section_id=intro_id,
                order_index=1,
                section_chunk_index=1,
                anchor=intro_chunk_2_anchor,
                content_hash=content_hash(intro_text_2),
                content_text=intro_text_2,
            ),
            Chunk(
                id=chunk_id(doc_id, detail_chunk_anchor),
                document_id=doc_id,
                section_id=detail_id,
                order_index=2,
                section_chunk_index=0,
                anchor=detail_chunk_anchor,
                content_hash=content_hash(detail_text),
                content_text=detail_text,
            ),
        ),
    )


def test_get_document_found_by_source_uri() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc()
    _ = sink.upsert([doc])

    stored = sink.get_document(doc.source_uri)

    assert stored == doc
    assert stored is not None
    assert len(stored.sections) == 1
    assert len(stored.chunks) == 1


def test_get_document_not_found_returns_none() -> None:
    sink = SQLAlchemySink(engine=_make_engine())

    stored = sink.get_document("file:missing.md")

    assert stored is None


def test_get_document_by_id_found_returns_full_document() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc()
    _ = sink.upsert([doc])

    stored = sink.get_document_by_id(doc.id)

    assert stored == doc
    assert stored is not None
    assert len(stored.sections) == 1
    assert len(stored.chunks) == 1


def test_list_documents_returns_expected_page_shape() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    first = _make_doc(source_uri="file:a.md", title="A", body="A body")
    second = _make_doc(source_uri="file:b.md", title="B", body="B body")
    _ = sink.upsert([first, second])

    page = sink.list_documents(offset=0, limit=1)

    assert isinstance(page, Page)
    assert page.total == 2
    assert page.offset == 0
    assert page.limit == 1
    assert page.has_more is True
    assert len(page.items) == 1


def test_list_documents_pagination_offset_one_limit_one_has_no_more() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    first = _make_doc(source_uri="file:a.md", title="A", body="A body")
    second = _make_doc(source_uri="file:b.md", title="B", body="B body")
    _ = sink.upsert([first, second])

    page = sink.list_documents(offset=1, limit=1)

    assert page.total == 2
    assert page.offset == 1
    assert page.limit == 1
    assert page.has_more is False
    assert len(page.items) == 1


def test_list_documents_empty_database_returns_empty_page() -> None:
    sink = SQLAlchemySink(engine=_make_engine())

    page = sink.list_documents()

    assert page.total == 0
    assert page.items == ()
    assert page.has_more is False


def test_list_documents_returns_lightweight_documents() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc()
    _ = sink.upsert([doc])

    page = sink.list_documents()

    assert len(page.items) == 1
    listed = page.items[0]
    assert isinstance(listed, Document)
    assert listed.sections == ()
    assert listed.chunks == ()


def test_get_section_found_by_id() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc()
    _ = sink.upsert([doc])
    section = doc.sections[0]

    stored = sink.get_section(section.id)

    assert stored == section


def test_get_section_not_found_returns_none() -> None:
    sink = SQLAlchemySink(engine=_make_engine())

    stored = sink.get_section(uuid.uuid4())

    assert stored is None


def test_list_sections_returns_ordered_sections() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc_with_multiple_sections_and_chunks()
    _ = sink.upsert([doc])

    page = sink.list_sections(doc.id)
    items = cast(tuple[Section, ...], page.items)

    assert page.total == 2
    assert [section.order_index for section in items] == [0, 1]


def test_list_sections_pagination_works() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc_with_multiple_sections_and_chunks()
    _ = sink.upsert([doc])

    page = sink.list_sections(doc.id, offset=1, limit=1)
    items = cast(tuple[Section, ...], page.items)

    assert page.total == 2
    assert len(items) == 1
    assert items[0].order_index == 1
    assert page.has_more is False


def test_get_chunk_found_by_id() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc()
    _ = sink.upsert([doc])
    chunk = doc.chunks[0]

    stored = sink.get_chunk(chunk.id)

    assert stored == chunk


def test_get_chunk_not_found_returns_none() -> None:
    sink = SQLAlchemySink(engine=_make_engine())

    stored = sink.get_chunk(uuid.uuid4())

    assert stored is None


def test_list_chunks_returns_ordered_chunks() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc_with_multiple_sections_and_chunks()
    _ = sink.upsert([doc])

    page = sink.list_chunks(doc.id)
    items = cast(tuple[Chunk, ...], page.items)

    assert page.total == 3
    assert [chunk.order_index for chunk in items] == [0, 1, 2]


def test_list_chunks_pagination_works() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc_with_multiple_sections_and_chunks()
    _ = sink.upsert([doc])

    page = sink.list_chunks(doc.id, offset=1, limit=1)
    items = cast(tuple[Chunk, ...], page.items)

    assert page.total == 3
    assert len(items) == 1
    assert items[0].order_index == 1
    assert page.has_more is True


def test_get_chunks_by_section_returns_only_section_chunks() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc_with_multiple_sections_and_chunks()
    _ = sink.upsert([doc])
    intro_section_id = doc.sections[0].id

    page = sink.get_chunks_by_section(intro_section_id)
    items = cast(tuple[Chunk, ...], page.items)

    assert page.total == 2
    assert len(items) == 2
    assert all(chunk.section_id == intro_section_id for chunk in items)
    assert [chunk.section_chunk_index for chunk in items] == [0, 1]


def test_stats_still_works() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc_with_multiple_sections_and_chunks()
    _ = sink.upsert([doc])

    stats = sink.stats()

    assert stats.documents == 1
    assert stats.sections == 2
    assert stats.chunks == 3


def test_query_api_returns_domain_types() -> None:
    sink = SQLAlchemySink(engine=_make_engine())
    doc = _make_doc_with_multiple_sections_and_chunks()
    _ = sink.upsert([doc])

    fetched_doc = sink.get_document(doc.source_uri)
    fetched_doc_by_id = sink.get_document_by_id(doc.id)
    fetched_section = sink.get_section(doc.sections[0].id)
    fetched_chunk = sink.get_chunk(doc.chunks[0].id)
    docs_page = sink.list_documents()
    sections_page = sink.list_sections(doc.id)
    chunks_page = sink.list_chunks(doc.id)
    by_section_page = sink.get_chunks_by_section(doc.sections[0].id)

    assert isinstance(fetched_doc, Document)
    assert isinstance(fetched_doc_by_id, Document)
    assert isinstance(fetched_section, Section)
    assert isinstance(fetched_chunk, Chunk)
    assert all(isinstance(item, Document) for item in docs_page.items)
    assert all(isinstance(item, Section) for item in sections_page.items)
    assert all(isinstance(item, Chunk) for item in chunks_page.items)
    assert all(isinstance(item, Chunk) for item in by_section_page.items)
