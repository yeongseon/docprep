from __future__ import annotations

from pathlib import Path
import uuid

import pytest

from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.token import TokenChunker
from docprep.eval import (
    AnswerSpan,
    EvalCorpus,
    EvalQuery,
    compute_chunking_metrics,
    compute_retrieval_metrics,
    run_benchmark,
)
from docprep.loaders.types import LoadedSource
from docprep.models.domain import Chunk, Document


def _chunk(
    document_id: uuid.UUID,
    source_uri: str,
    order_index: int,
    text: str,
    heading_path: tuple[str, ...] = (),
) -> Chunk:
    del source_uri
    return Chunk(
        id=uuid.uuid4(),
        document_id=document_id,
        section_id=uuid.uuid4(),
        order_index=order_index,
        section_chunk_index=order_index,
        content_text=text,
        heading_path=heading_path,
    )


def _doc(source_uri: str, chunks: tuple[Chunk, ...]) -> Document:
    return Document(
        id=chunks[0].document_id if chunks else uuid.uuid4(),
        source_uri=source_uri,
        title=Path(source_uri).name,
        source_checksum="checksum",
        chunks=chunks,
    )


def test_answer_span_and_eval_query_creation() -> None:
    span = AnswerSpan(
        text="pip install docprep", source_uri="file:README.md", start_char=10, end_char=29
    )
    query = EvalQuery(
        query="How do I install docprep?",
        answer_spans=(span,),
        relevant_doc_uris=("file:README.md",),
    )

    assert query.query == "How do I install docprep?"
    assert query.answer_spans[0].text == "pip install docprep"
    assert query.relevant_doc_uris == ("file:README.md",)


def test_eval_corpus_round_trip() -> None:
    corpus = EvalCorpus(
        name="sample",
        description="desc",
        source_dir="docs/",
        queries=(
            EvalQuery(
                query="install",
                answer_spans=(AnswerSpan(text="pip install docprep", source_uri="file:README.md"),),
                relevant_doc_uris=("file:README.md",),
            ),
        ),
    )

    rebuilt = EvalCorpus.from_dict(corpus.to_dict())
    assert rebuilt == corpus


def test_eval_corpus_save_and_load(tmp_path: Path) -> None:
    corpus = EvalCorpus(name="saved", source_dir="docs/")
    path = tmp_path / "corpus.json"

    corpus.save(path)
    loaded = EvalCorpus.load(path)

    assert loaded == corpus


def test_compute_chunking_metrics_known_values() -> None:
    doc_id_a = uuid.uuid4()
    doc_id_b = uuid.uuid4()
    docs = (
        _doc(
            "file:a.md",
            (
                _chunk(doc_id_a, "file:a.md", 0, "alpha", ("Intro",)),
                _chunk(doc_id_a, "file:a.md", 1, "beta gamma", ()),
            ),
        ),
        _doc(
            "file:b.md",
            (_chunk(doc_id_b, "file:b.md", 0, "delta", ("Guide",)),),
        ),
    )

    metrics = compute_chunking_metrics("cfg", docs, token_counter=lambda text: len(text.split()))

    assert metrics.chunker_name == "cfg"
    assert metrics.total_chunks == 3
    assert metrics.avg_chunk_chars == pytest.approx((5 + 10 + 5) / 3)
    assert metrics.avg_chunk_tokens == 1
    assert metrics.min_chunk_chars == 5
    assert metrics.max_chunk_chars == 10
    assert metrics.orphan_chunk_count == 1
    assert metrics.orphan_chunk_rate == pytest.approx(1 / 3)
    assert metrics.elapsed_seconds >= 0


def test_compute_retrieval_metrics_known_values() -> None:
    doc_id_a = uuid.uuid4()
    doc_id_b = uuid.uuid4()
    docs = (
        _doc(
            "file:README.md",
            (_chunk(doc_id_a, "file:README.md", 0, "Install with pip install docprep"),),
        ),
        _doc(
            "file:guide.md",
            (_chunk(doc_id_b, "file:guide.md", 0, "No matching answer in this document"),),
        ),
    )
    queries = (
        EvalQuery(
            query="install",
            answer_spans=(AnswerSpan(text="pip install docprep", source_uri="file:README.md"),),
        ),
        EvalQuery(
            query="missing",
            answer_spans=(AnswerSpan(text="this does not exist", source_uri="file:guide.md"),),
        ),
    )

    metrics = compute_retrieval_metrics("cfg", docs, queries)

    assert metrics.recall_at_1 == pytest.approx(0.5)
    assert metrics.recall_at_5 == pytest.approx(0.5)
    assert metrics.recall_at_10 == pytest.approx(0.5)
    assert metrics.citation_hit_rate == pytest.approx(0.5)
    assert metrics.mean_reciprocal_rank == pytest.approx(0.5)


def test_compute_retrieval_metrics_not_found_returns_zero() -> None:
    doc_id = uuid.uuid4()
    docs = (_doc("file:README.md", (_chunk(doc_id, "file:README.md", 0, "hello world"),)),)
    queries = (
        EvalQuery(
            query="missing",
            answer_spans=(AnswerSpan(text="not present", source_uri="file:README.md"),),
        ),
    )

    metrics = compute_retrieval_metrics("cfg", docs, queries)
    assert metrics.recall_at_1 == 0.0
    assert metrics.recall_at_5 == 0.0
    assert metrics.recall_at_10 == 0.0
    assert metrics.citation_hit_rate == 0.0
    assert metrics.mean_reciprocal_rank == 0.0


def test_run_benchmark_end_to_end_with_fixture_loader_parser() -> None:
    class FixtureLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [
                LoadedSource(
                    source_path="README.md",
                    source_uri="file:README.md",
                    raw_text="# Install\n\nRun `pip install docprep`.",
                    checksum="checksum-1",
                )
            ]

    class FixtureParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return Document(
                id=uuid.uuid4(),
                source_uri=loaded_source.source_uri,
                title="README",
                source_checksum=loaded_source.checksum,
                body_markdown=loaded_source.raw_text,
            )

    corpus = EvalCorpus(
        name="benchmark",
        source_dir="ignored",
        queries=(
            EvalQuery(
                query="install",
                answer_spans=(AnswerSpan(text="pip install docprep", source_uri="file:README.md"),),
            ),
        ),
    )

    results = run_benchmark(
        corpus,
        chunker_configs=(
            ("heading-only", (HeadingChunker(),)),
            ("heading+token", (HeadingChunker(), TokenChunker(max_tokens=16))),
        ),
        loader=FixtureLoader(),
        parser=FixtureParser(),
    )

    assert len(results) == 2
    assert results[0].chunking_metrics.chunker_name == "heading-only"
    assert results[1].chunking_metrics.chunker_name == "heading+token"
    assert results[0].chunking_metrics.total_chunks == 0
    assert results[1].chunking_metrics.total_chunks >= 1
    assert results[1].retrieval_metrics is not None
    assert results[1].retrieval_metrics.recall_at_1 == pytest.approx(1.0)


def test_run_benchmark_empty_queries_sets_retrieval_metrics_none() -> None:
    class FixtureLoader:
        def load(self, source: str | Path) -> list[LoadedSource]:
            del source
            return [
                LoadedSource(
                    source_path="README.md",
                    source_uri="file:README.md",
                    raw_text="# Install\n\nRun `pip install docprep`.",
                    checksum="checksum-1",
                )
            ]

    class FixtureParser:
        def parse(self, loaded_source: LoadedSource) -> Document:
            return Document(
                id=uuid.uuid4(),
                source_uri=loaded_source.source_uri,
                title="README",
                source_checksum=loaded_source.checksum,
                body_markdown=loaded_source.raw_text,
            )

    corpus = EvalCorpus(name="benchmark", source_dir="ignored", queries=())
    results = run_benchmark(
        corpus,
        chunker_configs=(("heading-only", (HeadingChunker(),)),),
        loader=FixtureLoader(),
        parser=FixtureParser(),
    )

    assert len(results) == 1
    assert results[0].retrieval_metrics is None
