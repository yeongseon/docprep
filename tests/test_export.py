from __future__ import annotations

import uuid

from docprep.export import build_vector_records
from docprep.models.domain import Chunk, Document, Section


def _document() -> Document:
    doc_id = uuid.uuid4()
    section = Section(
        id=uuid.uuid4(),
        document_id=doc_id,
        order_index=0,
        heading="Intro",
        heading_level=1,
        heading_path=("Intro",),
        lineage=("root",),
        content_markdown="Chunk body",
    )
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        section_id=section.id,
        order_index=2,
        section_chunk_index=0,
        content_text="Chunk body",
        heading_path=("Intro",),
        lineage=("root",),
    )
    return Document(
        id=doc_id,
        source_uri="docs/example.md",
        title="Example",
        source_checksum="checksum",
        frontmatter={"author": "Ada"},
        sections=(section,),
        chunks=(chunk,),
    )


def test_build_vector_records_creates_one_record_per_chunk() -> None:
    document = _document()
    records = build_vector_records((document,))

    assert len(records) == 1
    assert records[0].id == document.chunks[0].id


def test_vector_record_text_includes_title_heading_path_and_content() -> None:
    document = _document()

    record = build_vector_records((document,))[0]

    assert record.text == "Example\n\nIntro\n\nChunk body"


def test_vector_record_metadata_includes_required_fields() -> None:
    document = _document()

    metadata = build_vector_records((document,))[0].metadata

    assert metadata == {
        "document_id": str(document.id),
        "source_uri": document.source_uri,
        "section_id": str(document.chunks[0].section_id),
        "heading_path": ["Intro"],
        "lineage": ["root"],
        "frontmatter": {"author": "Ada"},
        "source_type": "markdown",
        "chunk_order_index": 2,
        "section_chunk_index": 0,
    }


def test_empty_documents_return_empty_tuple() -> None:
    assert build_vector_records(()) == ()
