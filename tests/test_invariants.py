from __future__ import annotations

from pathlib import Path
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.size import SizeChunker
from docprep.ingest import Ingestor


def _ingest_text(text: str, *, max_chars: int | None = None):
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "sample.md"
        _ = path.write_text(text, encoding="utf-8")
        if max_chars is None:
            return Ingestor().run(path)
        return Ingestor(chunkers=[HeadingChunker(), SizeChunker(max_chars=max_chars)]).run(path)


def _ingest_path(path: Path, *, max_chars: int | None = None):
    if max_chars is None:
        return Ingestor().run(path)
    return Ingestor(chunkers=[HeadingChunker(), SizeChunker(max_chars=max_chars)]).run(path)


def _normalize(text: str) -> str:
    return "".join(text.split())


@given(text=st.text(min_size=1, max_size=5000))
@settings(max_examples=40)
def test_chunk_coverage_no_content_lost(text: str) -> None:
    payload = f"content\n\n{text}"
    result = _ingest_text(payload)

    assert len(result.documents) == 1
    document = result.documents[0]
    section_body = "\n".join(section.content_markdown for section in document.sections)
    chunk_body = "\n".join(chunk.content_text for chunk in document.chunks)

    assert _normalize(section_body) in _normalize(chunk_body)
    assert all(chunk.content_text.strip() for chunk in document.chunks)
    assert [section.order_index for section in document.sections] == list(
        range(len(document.sections))
    )
    assert [chunk.order_index for chunk in document.chunks] == list(range(len(document.chunks)))


@given(text=st.from_regex(r"(#{1,6} .+\n\n.+\n)+", fullmatch=True))
@settings(max_examples=30)
def test_uuid_determinism(text: str) -> None:
    payload = f"{text}\n"
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "stable.md"
        _ = path.write_text(payload, encoding="utf-8")
        first = _ingest_path(path)
        second = _ingest_path(path)

    assert len(first.documents) == len(second.documents) == 1
    first_doc = first.documents[0]
    second_doc = second.documents[0]

    assert first_doc.id == second_doc.id
    assert [section.id for section in first_doc.sections] == [
        section.id for section in second_doc.sections
    ]
    assert [chunk.id for chunk in first_doc.chunks] == [chunk.id for chunk in second_doc.chunks]


@given(max_chars=st.integers(min_value=100, max_value=5000))
@settings(max_examples=35)
def test_chunk_size_respects_max_chars(max_chars: int) -> None:
    text = "# Size test\n\n" + ("0123456789 " * 1200)
    result = _ingest_text(text, max_chars=max_chars)

    assert len(result.documents) == 1
    document = result.documents[0]
    assert len(document.chunks) >= 1
    assert all(0 < len(chunk.content_text) <= max_chars for chunk in document.chunks)
