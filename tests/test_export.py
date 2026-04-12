from __future__ import annotations

import uuid

from docprep import __version__
from docprep.export import build_vector_records, build_vector_records_v1
from docprep.ids import SCHEMA_VERSION
from docprep.models.domain import Chunk, Document, Section, TextPrependStrategy, VectorRecordV1


def _document() -> Document:
    doc_id = uuid.uuid4()
    section = Section(
        id=uuid.uuid4(),
        document_id=doc_id,
        order_index=0,
        heading="Intro",
        heading_level=1,
        anchor="intro",
        content_hash="aaaaaaaaaaaaaaaa",
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
        anchor="intro:bbbbbbbbbbbbbbbb",
        content_hash="bbbbbbbbbbbbbbbb",
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
        "docprep.chunk_anchor": "intro:bbbbbbbbbbbbbbbb",
        "docprep.chunk_order_index": 2,
        "docprep.section_chunk_index": 0,
        "docprep.schema_version": SCHEMA_VERSION,
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
        "docprep.chunk_anchor",
        "docprep.chunk_order_index",
        "docprep.section_chunk_index",
        "docprep.schema_version",
    }


def test_empty_documents_return_empty_tuple() -> None:
    assert build_vector_records(()) == ()


def test_build_vector_records_v1_creates_typed_records() -> None:
    document = _document()

    records = build_vector_records_v1((document,), created_at="2026-01-01T00:00:00+00:00")

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, VectorRecordV1)
    assert record.id == document.chunks[0].id
    assert record.document_id == document.id
    assert record.section_id == document.chunks[0].section_id
    assert record.chunk_anchor == document.chunks[0].anchor
    assert record.section_anchor == document.sections[0].anchor
    assert record.text == "Example\n\nIntro\n\nChunk body"
    assert record.source_uri == document.source_uri
    assert record.title == document.title
    assert record.section_path == ("Intro",)
    assert record.user_metadata == {"author": "Ada", "lang": "en"}


def test_v1_record_has_provenance() -> None:
    record = build_vector_records_v1((_document(),), created_at="2026-02-03T04:05:06+00:00")[0]

    assert record.pipeline_version == __version__
    assert record.created_at == "2026-02-03T04:05:06+00:00"
    assert record.schema_version == SCHEMA_VERSION


def test_v1_record_has_content_metrics() -> None:
    document = _document()

    record = build_vector_records_v1((document,), created_at="2026-02-03T04:05:06+00:00")[0]

    assert record.char_count == len(document.chunks[0].content_text)
    assert record.content_hash == document.chunks[0].content_hash


def test_text_prepend_none() -> None:
    record = build_vector_records_v1((_document(),), text_prepend=TextPrependStrategy.NONE)[0]

    assert record.text == "Chunk body"


def test_text_prepend_title_only() -> None:
    record = build_vector_records_v1((_document(),), text_prepend=TextPrependStrategy.TITLE_ONLY)[0]

    assert record.text == "Example\n\nChunk body"


def test_text_prepend_heading_path() -> None:
    record = build_vector_records_v1((_document(),), text_prepend=TextPrependStrategy.HEADING_PATH)[
        0
    ]

    assert record.text == "Intro\n\nChunk body"


def test_text_prepend_title_and_heading_path() -> None:
    record = build_vector_records_v1(
        (_document(),),
        text_prepend=TextPrependStrategy.TITLE_AND_HEADING_PATH,
    )[0]

    assert record.text == "Example\n\nIntro\n\nChunk body"


def test_legacy_build_vector_records_still_works() -> None:
    record = build_vector_records((_document(),))[0]

    assert record.text == "Example\n\nIntro\n\nChunk body"
    assert record.metadata["docprep.schema_version"] == SCHEMA_VERSION
