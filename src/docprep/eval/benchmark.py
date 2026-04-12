from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
import time

from ..chunkers.protocol import Chunker
from ..loaders.filesystem import FileSystemLoader
from ..loaders.protocol import Loader
from ..models.domain import Chunk, Document
from ..parsers.multi import MultiFormatParser
from ..parsers.protocol import Parser
from .corpus import EvalCorpus, EvalQuery


@dataclass(frozen=True, slots=True)
class ChunkingMetrics:
    chunker_name: str
    total_chunks: int
    avg_chunk_chars: float
    avg_chunk_tokens: int | None
    min_chunk_chars: int
    max_chunk_chars: int
    orphan_chunk_count: int
    orphan_chunk_rate: float
    elapsed_seconds: float


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    chunker_name: str
    recall_at_1: float
    recall_at_5: float
    recall_at_10: float
    citation_hit_rate: float
    mean_reciprocal_rank: float


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    chunking_metrics: ChunkingMetrics
    retrieval_metrics: RetrievalMetrics | None = None

    def to_dict(self) -> dict[str, object]:
        retrieval_metrics: dict[str, object] | None = None
        if self.retrieval_metrics is not None:
            retrieval_metrics = {
                "chunker_name": self.retrieval_metrics.chunker_name,
                "recall_at_1": self.retrieval_metrics.recall_at_1,
                "recall_at_5": self.retrieval_metrics.recall_at_5,
                "recall_at_10": self.retrieval_metrics.recall_at_10,
                "citation_hit_rate": self.retrieval_metrics.citation_hit_rate,
                "mean_reciprocal_rank": self.retrieval_metrics.mean_reciprocal_rank,
            }

        return {
            "chunking_metrics": {
                "chunker_name": self.chunking_metrics.chunker_name,
                "total_chunks": self.chunking_metrics.total_chunks,
                "avg_chunk_chars": self.chunking_metrics.avg_chunk_chars,
                "avg_chunk_tokens": self.chunking_metrics.avg_chunk_tokens,
                "min_chunk_chars": self.chunking_metrics.min_chunk_chars,
                "max_chunk_chars": self.chunking_metrics.max_chunk_chars,
                "orphan_chunk_count": self.chunking_metrics.orphan_chunk_count,
                "orphan_chunk_rate": self.chunking_metrics.orphan_chunk_rate,
                "elapsed_seconds": self.chunking_metrics.elapsed_seconds,
            },
            "retrieval_metrics": retrieval_metrics,
        }


def compute_chunking_metrics(
    chunker_name: str,
    documents: tuple[Document, ...],
    token_counter: Callable[[str], int] | None = None,
) -> ChunkingMetrics:
    started = time.perf_counter()
    chunk_records = _all_chunks(documents)
    chunks = [chunk for _, chunk in chunk_records]
    char_counts = [len(chunk.content_text) for chunk in chunks]
    total_chunks = len(char_counts)
    total_chars = sum(char_counts)
    avg_chunk_chars = (float(total_chars) / total_chunks) if total_chunks else 0.0

    avg_chunk_tokens: int | None = None
    if token_counter is not None:
        token_counts = [max(0, int(token_counter(chunk.content_text))) for chunk in chunks]
        avg_chunk_tokens = (sum(token_counts) // len(token_counts)) if token_counts else 0

    orphan_chunk_count = sum(1 for chunk in chunks if not chunk.heading_path)
    orphan_chunk_rate = (float(orphan_chunk_count) / total_chunks) if total_chunks else 0.0
    elapsed_seconds = time.perf_counter() - started

    return ChunkingMetrics(
        chunker_name=chunker_name,
        total_chunks=total_chunks,
        avg_chunk_chars=avg_chunk_chars,
        avg_chunk_tokens=avg_chunk_tokens,
        min_chunk_chars=min(char_counts) if char_counts else 0,
        max_chunk_chars=max(char_counts) if char_counts else 0,
        orphan_chunk_count=orphan_chunk_count,
        orphan_chunk_rate=orphan_chunk_rate,
        elapsed_seconds=elapsed_seconds,
    )


def compute_retrieval_metrics(
    chunker_name: str,
    documents: tuple[Document, ...],
    queries: tuple[EvalQuery, ...],
) -> RetrievalMetrics:
    chunk_records = _all_chunks(documents)
    if not queries:
        return RetrievalMetrics(
            chunker_name=chunker_name,
            recall_at_1=0.0,
            recall_at_5=0.0,
            recall_at_10=0.0,
            citation_hit_rate=0.0,
            mean_reciprocal_rank=0.0,
        )

    recall_1_hits = 0
    recall_5_hits = 0
    recall_10_hits = 0
    reciprocal_rank_sum = 0.0
    total_spans = 0
    found_spans = 0

    for query in queries:
        spans = query.answer_spans
        for span in spans:
            total_spans += 1
            if _span_found(span.text, span.source_uri, chunk_records):
                found_spans += 1

        scored = sorted(
            (
                (_chunk_score(source_uri, chunk, query), chunk.order_index)
                for source_uri, chunk in chunk_records
            ),
            key=lambda item: (-item[0], item[1]),
        )
        ranked_scores = [score for score, _ in scored]
        if _has_hit(ranked_scores, 1):
            recall_1_hits += 1
        if _has_hit(ranked_scores, 5):
            recall_5_hits += 1
        if _has_hit(ranked_scores, 10):
            recall_10_hits += 1

        rank = _first_hit_rank(ranked_scores)
        reciprocal_rank_sum += (1.0 / rank) if rank > 0 else 0.0

    query_count = len(queries)
    citation_hit_rate = (float(found_spans) / total_spans) if total_spans else 0.0
    return RetrievalMetrics(
        chunker_name=chunker_name,
        recall_at_1=float(recall_1_hits) / query_count,
        recall_at_5=float(recall_5_hits) / query_count,
        recall_at_10=float(recall_10_hits) / query_count,
        citation_hit_rate=citation_hit_rate,
        mean_reciprocal_rank=reciprocal_rank_sum / query_count,
    )


def run_benchmark(
    corpus: EvalCorpus,
    chunker_configs: Sequence[tuple[str, tuple[Chunker, ...]]],
    loader: Loader | None = None,
    parser: Parser | None = None,
) -> tuple[BenchmarkResult, ...]:
    bench_loader: Loader = loader if loader is not None else FileSystemLoader()
    bench_parser: Parser = parser if parser is not None else MultiFormatParser()

    results: list[BenchmarkResult] = []
    for chunker_name, chunkers in chunker_configs:
        started = time.perf_counter()
        documents = _process_documents(corpus.source_dir, bench_loader, bench_parser, chunkers)
        elapsed_seconds = time.perf_counter() - started

        chunking_metrics = compute_chunking_metrics(chunker_name, documents)
        chunking_metrics = replace(chunking_metrics, elapsed_seconds=elapsed_seconds)
        retrieval_metrics = None
        if corpus.queries:
            retrieval_metrics = compute_retrieval_metrics(chunker_name, documents, corpus.queries)

        results.append(
            BenchmarkResult(
                chunking_metrics=chunking_metrics,
                retrieval_metrics=retrieval_metrics,
            )
        )

    return tuple(results)


def _process_documents(
    source_dir: str,
    loader: Loader,
    parser: Parser,
    chunkers: tuple[Chunker, ...],
) -> tuple[Document, ...]:
    documents: list[Document] = []
    for loaded_source in loader.load(source_dir):
        document = parser.parse(loaded_source)
        for chunker in chunkers:
            document = chunker.chunk(document)
        documents.append(document)
    return tuple(documents)


def _all_chunks(documents: tuple[Document, ...]) -> list[tuple[str, Chunk]]:
    chunks: list[tuple[str, Chunk]] = []
    for document in documents:
        chunks.extend((document.source_uri, chunk) for chunk in document.chunks)
    return chunks


def _chunk_score(source_uri: str, chunk: Chunk, query: EvalQuery) -> int:
    score = 0
    content = chunk.content_text.casefold()
    for span in query.answer_spans:
        if span.source_uri and span.source_uri != source_uri:
            continue
        if span.text.casefold() in content:
            score += 1
    return score


def _span_found(span_text: str, source_uri: str, chunks: list[tuple[str, Chunk]]) -> bool:
    needle = span_text.casefold()
    for chunk_source_uri, chunk in chunks:
        if source_uri and source_uri != chunk_source_uri:
            continue
        if needle in chunk.content_text.casefold():
            return True
    return False


def _has_hit(ranked_scores: list[int], k: int) -> bool:
    return any(score > 0 for score in ranked_scores[:k])


def _first_hit_rank(ranked_scores: list[int]) -> int:
    for index, score in enumerate(ranked_scores, start=1):
        if score > 0:
            return index
    return 0
