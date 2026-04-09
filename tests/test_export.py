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
        source_metadata={"author": "Grace", "lang": "en"},
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


def test_vector_record_metadata_flattens_user_and_system_fields() -> None:
    document = _document()

    metadata = build_vector_records((document,))[0].metadata

    assert metadata == {
        "author": "Ada",
        "lang": "en",
        "docprep.document_id": str(document.id),
        "docprep.source_uri": document.source_uri,
        "docprep.source_type": "markdown",
        "docprep.section_id": str(document.chunks[0].section_id),
        "docprep.heading_path": ["Intro"],
        "docprep.lineage": ["root"],
        "docprep.chunk_order_index": 2,
        "docprep.section_chunk_index": 0,
    }


def test_frontmatter_metadata_overrides_source_metadata_at_top_level() -> None:
    metadata = build_vector_records((_document(),))[0].metadata

    assert metadata["author"] == "Ada"
    assert metadata["lang"] == "en"
    assert "frontmatter" not in metadata


def test_all_system_metadata_keys_use_docprep_namespace() -> None:
    metadata = build_vector_records((_document(),))[0].metadata

    system_keys = {key for key in metadata if key.startswith("docprep.")}

    assert system_keys == {
        "docprep.document_id",
        "docprep.source_uri",
        "docprep.source_type",
        "docprep.section_id",
        "docprep.heading_path",
        "docprep.lineage",
        "docprep.chunk_order_index",
        "docprep.section_chunk_index",
    }


def test_empty_documents_return_empty_tuple() -> None:
    assert build_vector_records(()) == ()
