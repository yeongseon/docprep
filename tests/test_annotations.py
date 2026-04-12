from __future__ import annotations

from dataclasses import replace
import uuid

from docprep.chunkers._markdown import extract_structural_annotations
from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker
from docprep.chunkers.token import TokenChunker
from docprep.export import build_vector_records
from docprep.ids import content_hash as compute_content_hash
from docprep.loaders.types import LoadedSource
from docprep.models.domain import Chunk, Document, StructureKind
from docprep.parsers.html import HtmlParser
from docprep.parsers.markdown import MarkdownParser


def _loaded_markdown(raw_text: str) -> LoadedSource:
    return LoadedSource(
        source_path="docs/example.md",
        source_uri="docs/example.md",
        raw_text=raw_text,
        checksum="checksum",
    )


def _loaded_html(raw_text: str) -> LoadedSource:
    return LoadedSource(
        source_path="docs/example.html",
        source_uri="docs/example.html",
        raw_text=raw_text,
        checksum="checksum",
        media_type="text/html",
    )


def _document_with_chunk(text: str, *, structure_types: tuple[str, ...] = ()) -> Document:
    doc_id = uuid.uuid4()
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=doc_id,
        section_id=uuid.uuid4(),
        order_index=0,
        section_chunk_index=0,
        content_text=text,
        content_hash=compute_content_hash(text),
        structure_types=structure_types,
    )
    return Document(
        id=doc_id,
        source_uri="docs/example.md",
        title="Example",
        source_checksum="checksum",
        chunks=(chunk,),
    )


def test_structure_kind_values() -> None:
    assert StructureKind.CODE_FENCE.value == "code_fence"
    assert StructureKind.TABLE.value == "table"
    assert StructureKind.LIST.value == "list"


def test_extract_structural_annotations_code_fence_span() -> None:
    text = "before\n\n```python\nprint('x')\n```\n\nafter"

    annotations = extract_structural_annotations(text)

    code_annotations = [item for item in annotations if item.kind is StructureKind.CODE_FENCE]
    assert len(code_annotations) == 1
    span_text = text[code_annotations[0].char_start : code_annotations[0].char_end]
    assert span_text == "```python\nprint('x')\n```\n"


def test_extract_structural_annotations_table_and_list_are_grouped() -> None:
    text = "\n".join(
        (
            "| H1 | H2 |",
            "| --- | --- |",
            "| r1 | v1 |",
            "| r2 | v2 |",
            "",
            "- one",
            "- two",
            "- three",
        )
    )

    annotations = extract_structural_annotations(text)

    table_annotations = [item for item in annotations if item.kind is StructureKind.TABLE]
    list_annotations = [item for item in annotations if item.kind is StructureKind.LIST]
    assert len(table_annotations) == 1
    assert len(list_annotations) == 1


def test_extract_structural_annotations_all_three_and_plain_text() -> None:
    rich_text = "\n\n".join(
        (
            "```\ncode\n```",
            "| A | B |\n| --- | --- |",
            "- one\n- two",
        )
    )

    kinds = {item.kind for item in extract_structural_annotations(rich_text)}

    assert kinds == {StructureKind.CODE_FENCE, StructureKind.TABLE, StructureKind.LIST}
    assert extract_structural_annotations("just words") == ()


def test_markdown_parser_emits_structural_annotations() -> None:
    parsed = MarkdownParser().parse(
        _loaded_markdown("```\nprint('x')\n```\n\n| A | B |\n| --- | --- |")
    )

    kinds = {item.kind for item in parsed.structural_annotations}

    assert StructureKind.CODE_FENCE in kinds
    assert StructureKind.TABLE in kinds


def test_html_parser_emits_structural_annotations() -> None:
    parsed = HtmlParser().parse(
        _loaded_html(
            "<pre><code>x = 1</code></pre><table><tr><td>A</td></tr></table><ul><li>one</li></ul>"
        )
    )

    kinds = {item.kind for item in parsed.structural_annotations}

    assert kinds == {StructureKind.CODE_FENCE, StructureKind.TABLE, StructureKind.LIST}


def test_markdown_html_annotation_parity() -> None:
    markdown_doc = MarkdownParser().parse(
        _loaded_markdown("```\nprint('x')\n```\n\n| A | B |\n| --- | --- |\n\n- one\n- two")
    )
    html_doc = HtmlParser().parse(
        _loaded_html(
            "<pre><code>print('x')</code></pre><table><tr><td>A</td><td>B</td></tr></table><ul><li>one</li><li>two</li></ul>"
        )
    )

    md_kinds = {item.kind.value for item in markdown_doc.structural_annotations}
    html_kinds = {item.kind.value for item in html_doc.structural_annotations}

    assert md_kinds == html_kinds


def test_chunk_structure_types_tagging() -> None:
    code_doc = MarkdownParser().parse(_loaded_markdown("```\nprint('x')\n```"))
    code_chunked = SizeChunker(max_chars=200).chunk(HeadingChunker().chunk(code_doc))
    assert code_chunked.chunks[0].structure_types == ("code_fence",)

    table_list_doc = MarkdownParser().parse(
        _loaded_markdown("| A | B |\n| --- | --- |\n\n- one\n- two")
    )
    table_list_chunked = SizeChunker(max_chars=200).chunk(HeadingChunker().chunk(table_list_doc))
    assert set(table_list_chunked.chunks[0].structure_types) == {"table", "list"}

    plain_doc = MarkdownParser().parse(_loaded_markdown("plain text only"))
    plain_chunked = SizeChunker(max_chars=200).chunk(HeadingChunker().chunk(plain_doc))
    assert plain_chunked.chunks[0].structure_types == ()


def test_token_chunker_structure_types_tagging() -> None:
    document = MarkdownParser().parse(_loaded_markdown("- one\n- two\n\n```\ncode\n```"))

    chunked = TokenChunker(max_tokens=100).chunk(HeadingChunker().chunk(document))

    assert set(chunked.chunks[0].structure_types) == {"list", "code_fence"}


def test_export_include_annotations_toggle() -> None:
    document = _document_with_chunk("chunk", structure_types=("list", "table"))

    excluded = build_vector_records((document,), include_annotations=False)[0]
    included = build_vector_records((document,), include_annotations=True)[0]

    assert "docprep.structure_types" not in excluded.metadata
    assert included.metadata["docprep.structure_types"] == ["list", "table"]


def test_content_hash_unchanged_by_annotation_export_toggle() -> None:
    document = _document_with_chunk("```\nprint('x')\n```", structure_types=("code_fence",))

    no_annotations = build_vector_records((document,), include_annotations=False)[0]
    with_annotations = build_vector_records((document,), include_annotations=True)[0]

    assert no_annotations.id == with_annotations.id
    assert document.chunks[0].content_hash == compute_content_hash(document.chunks[0].content_text)


def test_document_and_chunk_annotation_defaults() -> None:
    base_document = _document_with_chunk("chunk")
    default_chunk = replace(base_document.chunks[0], structure_types=())
    default_document = replace(base_document, structural_annotations=(), chunks=(default_chunk,))

    assert default_document.structural_annotations == ()
    assert default_document.chunks[0].structure_types == ()
