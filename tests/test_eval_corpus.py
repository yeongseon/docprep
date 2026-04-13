"""Tests for eval/corpus.py — load, save, from_dict, _as_optional_int."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from docprep.eval.corpus import AnswerSpan, EvalCorpus, EvalQuery, _as_optional_int

# --- _as_optional_int edge cases ---


def test_as_optional_int_none() -> None:
    assert _as_optional_int(None) is None


def test_as_optional_int_bool_true() -> None:
    assert _as_optional_int(True) == 1


def test_as_optional_int_bool_false() -> None:
    assert _as_optional_int(False) == 0


def test_as_optional_int_int() -> None:
    assert _as_optional_int(42) == 42


def test_as_optional_int_float() -> None:
    assert _as_optional_int(3.7) == 3


def test_as_optional_int_str_valid() -> None:
    assert _as_optional_int("  10  ") == 10


def test_as_optional_int_str_empty() -> None:
    assert _as_optional_int("  ") is None


def test_as_optional_int_str_invalid() -> None:
    assert _as_optional_int("abc") is None


def test_as_optional_int_unsupported_type() -> None:
    assert _as_optional_int([1, 2]) is None


# --- EvalCorpus.from_dict edge cases ---


def test_from_dict_non_dict_query_skipped() -> None:
    data: dict[str, object] = {
        "name": "test",
        "queries": ["not-a-dict", 42, {"query": "valid"}],
    }
    corpus = EvalCorpus.from_dict(data)
    assert len(corpus.queries) == 1
    assert corpus.queries[0].query == "valid"


def test_from_dict_non_dict_span_skipped() -> None:
    data: dict[str, object] = {
        "name": "test",
        "queries": [
            {
                "query": "q1",
                "answer_spans": [
                    "not-a-dict",
                    {"text": "ok", "source_uri": "file:a.md"},
                ],
            }
        ],
    }
    corpus = EvalCorpus.from_dict(data)
    assert len(corpus.queries[0].answer_spans) == 1
    assert corpus.queries[0].answer_spans[0].text == "ok"


def test_from_dict_non_list_queries() -> None:
    data: dict[str, object] = {"name": "test", "queries": "not-a-list"}
    corpus = EvalCorpus.from_dict(data)
    assert len(corpus.queries) == 0


def test_from_dict_non_list_spans() -> None:
    data: dict[str, object] = {
        "name": "test",
        "queries": [{"query": "q1", "answer_spans": "not-a-list"}],
    }
    corpus = EvalCorpus.from_dict(data)
    assert len(corpus.queries[0].answer_spans) == 0


def test_from_dict_non_list_relevant_uris() -> None:
    data: dict[str, object] = {
        "name": "test",
        "queries": [{"query": "q1", "relevant_doc_uris": "not-a-list"}],
    }
    corpus = EvalCorpus.from_dict(data)
    assert len(corpus.queries[0].relevant_doc_uris) == 0


# --- EvalCorpus.load ---


def test_load_valid_json(tmp_path: Path) -> None:
    data = {
        "name": "benchmark",
        "description": "A test corpus",
        "source_dir": "docs/",
        "queries": [
            {
                "query": "What is docprep?",
                "answer_spans": [
                    {
                        "text": "document ingestion",
                        "source_uri": "file:readme.md",
                        "start_char": 0,
                        "end_char": 18,
                    }
                ],
                "relevant_doc_uris": ["file:readme.md"],
            }
        ],
    }
    path = tmp_path / "corpus.json"
    _ = path.write_text(json.dumps(data), encoding="utf-8")

    corpus = EvalCorpus.load(path)
    assert corpus.name == "benchmark"
    assert len(corpus.queries) == 1
    assert corpus.queries[0].answer_spans[0].start_char == 0


def test_load_non_object_root_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    _ = path.write_text("[1,2,3]", encoding="utf-8")

    with pytest.raises(ValueError, match="root must be an object"):
        EvalCorpus.load(path)


# --- EvalCorpus.save ---


def test_save_creates_file(tmp_path: Path) -> None:
    corpus = EvalCorpus(
        name="test",
        description="desc",
        source_dir="src/",
        queries=(
            EvalQuery(
                query="q",
                answer_spans=(
                    AnswerSpan(text="a", source_uri="file:a.md", start_char=0, end_char=1),
                ),
                relevant_doc_uris=("file:a.md",),
            ),
        ),
    )
    output = tmp_path / "sub" / "out.json"
    corpus.save(output)

    assert output.exists()
    loaded = json.loads(output.read_text(encoding="utf-8"))
    assert loaded["name"] == "test"
    assert len(loaded["queries"]) == 1


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    corpus = EvalCorpus(
        name="round",
        queries=(EvalQuery(query="x"),),
    )
    path = tmp_path / "rt.json"
    corpus.save(path)
    loaded = EvalCorpus.load(path)
    assert loaded.name == "round"
    assert loaded.queries[0].query == "x"
