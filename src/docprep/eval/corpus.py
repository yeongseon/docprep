"""Evaluation corpus format for chunking experiments."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import cast


@dataclass(frozen=True, slots=True)
class AnswerSpan:
    text: str
    source_uri: str
    start_char: int | None = None
    end_char: int | None = None


@dataclass(frozen=True, slots=True)
class EvalQuery:
    query: str
    answer_spans: tuple[AnswerSpan, ...] = ()
    relevant_doc_uris: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EvalCorpus:
    name: str
    description: str = ""
    source_dir: str = ""
    queries: tuple[EvalQuery, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "source_dir": self.source_dir,
            "queries": [
                {
                    "query": query.query,
                    "answer_spans": [
                        {
                            "text": span.text,
                            "source_uri": span.source_uri,
                            "start_char": span.start_char,
                            "end_char": span.end_char,
                        }
                        for span in query.answer_spans
                    ],
                    "relevant_doc_uris": list(query.relevant_doc_uris),
                }
                for query in self.queries
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> EvalCorpus:
        raw_queries = data.get("queries", [])
        queries: list[EvalQuery] = []
        query_items = cast(list[object], raw_queries) if isinstance(raw_queries, list) else []
        for raw_query_obj in query_items:
            if not isinstance(raw_query_obj, dict):
                continue
            raw_query = cast(dict[str, object], raw_query_obj)

            raw_spans = raw_query.get("answer_spans", [])
            spans: list[AnswerSpan] = []
            span_items = cast(list[object], raw_spans) if isinstance(raw_spans, list) else []
            for raw_span_obj in span_items:
                if not isinstance(raw_span_obj, dict):
                    continue
                raw_span = cast(dict[str, object], raw_span_obj)
                spans.append(
                    AnswerSpan(
                        text=str(raw_span.get("text", "")),
                        source_uri=str(raw_span.get("source_uri", "")),
                        start_char=_as_optional_int(raw_span.get("start_char")),
                        end_char=_as_optional_int(raw_span.get("end_char")),
                    )
                )

            raw_relevant = raw_query.get("relevant_doc_uris", [])
            relevant_items = (
                cast(list[object], raw_relevant) if isinstance(raw_relevant, list) else []
            )
            relevant = tuple(str(uri) for uri in relevant_items)
            queries.append(
                EvalQuery(
                    query=str(raw_query.get("query", "")),
                    answer_spans=tuple(spans),
                    relevant_doc_uris=relevant,
                )
            )

        return cls(
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            source_dir=str(data.get("source_dir", "")),
            queries=tuple(queries),
        )

    @classmethod
    def load(cls, path: str | Path) -> EvalCorpus:
        with Path(path).open("r", encoding="utf-8") as handle:
            data = cast(object, json.load(handle))
        if not isinstance(data, dict):
            raise ValueError("Evaluation corpus JSON root must be an object")
        return cls.from_dict(cast(dict[str, object], data))

    def save(self, path: str | Path) -> None:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2)
            _ = handle.write("\n")


def _as_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None
