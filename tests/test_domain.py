from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from typing import TypeAlias
import uuid

import pytest

from docprep.metadata import Metadata
from docprep.models.domain import Chunk, Document, IngestResult, Section, VectorRecord

DomainDataclass: TypeAlias = (
    type[Section] | type[Chunk] | type[Document] | type[VectorRecord] | type[IngestResult]
)


def _make_document() -> Document:
    return Document(
        id=uuid.uuid4(),
        source_uri="docs/example.md",
        title="Example",
        source_checksum="abc123",
    )


@pytest.mark.parametrize("cls", [Section, Chunk, Document, VectorRecord, IngestResult])
def test_all_domain_dataclasses_use_kw_only(cls: DomainDataclass) -> None:
    assert all(field.kw_only for field in fields(cls))


@pytest.mark.parametrize(
    ("instance", "attribute", "value"),
    [
        (
            Section(id=uuid.uuid4(), document_id=uuid.uuid4(), order_index=0),
            "heading",
            "new",
        ),
        (
            Chunk(
                id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                section_id=uuid.uuid4(),
                order_index=0,
                section_chunk_index=0,
                content_text="body",
            ),
            "content_text",
            "new",
        ),
        (_make_document(), "title", "Updated"),
        (VectorRecord(id=uuid.uuid4(), text="body"), "text", "Updated"),
        (IngestResult(documents=()), "persisted", True),
    ],
)
def test_all_domain_dataclasses_are_frozen(instance: object, attribute: str, value: object) -> None:
    with pytest.raises(FrozenInstanceError):
        setattr(instance, attribute, value)


@pytest.mark.parametrize("cls", [Section, Chunk, Document, VectorRecord, IngestResult])
def test_all_domain_dataclasses_use_slots(cls: DomainDataclass) -> None:
    assert hasattr(cls, "__slots__")


def test_document_default_values_work() -> None:
    document = _make_document()

    assert document.source_type == "markdown"
    assert document.frontmatter == {}
    assert document.source_metadata == {}
    assert document.body_markdown == ""
    assert document.sections == ()
    assert document.chunks == ()


def test_can_create_all_domain_objects_with_required_fields() -> None:
    document_id = uuid.uuid4()
    section = Section(id=uuid.uuid4(), document_id=document_id, order_index=0)
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document_id,
        section_id=section.id,
        order_index=0,
        section_chunk_index=0,
        content_text="content",
    )
    document = Document(
        id=document_id,
        source_uri="docs/example.md",
        title="Example",
        source_checksum="checksum",
    )
    record = VectorRecord(id=uuid.uuid4(), text="vector text")
    result = IngestResult(documents=(document,))

    assert section.document_id == document_id
    assert chunk.section_id == section.id
    assert document.title == "Example"
    assert record.metadata == {}
    assert result.documents == (document,)


def test_metadata_fields_use_metadata_type_alias() -> None:
    assert Document.__annotations__["frontmatter"] == "Metadata"
    assert Document.__annotations__["source_metadata"] == "Metadata"
    assert VectorRecord.__annotations__["metadata"] == "Metadata"
    assert Metadata is not None
