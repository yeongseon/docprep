# Evaluation Corpus

## Creating a corpus

Define a JSON file with:
- `name`: corpus identifier
- `description`: short purpose statement
- `source_dir`: directory to ingest for benchmark runs
- `queries`: query objects with `answer_spans` and optional `relevant_doc_uris`

Each answer span should include:
- `text`: expected answer text
- `source_uri`: source document URI where the answer should appear
- `start_char`/`end_char` (optional): character offsets when known

## Running a benchmark

```python
from docprep.eval import EvalCorpus, run_benchmark
from docprep.chunkers.heading import HeadingChunker
from docprep.chunkers.token import TokenChunker

corpus = EvalCorpus.load("examples/eval/sample_corpus.json")

results = run_benchmark(
    corpus,
    chunker_configs=[
        ("heading-only", (HeadingChunker(),)),
        ("heading+token-512", (HeadingChunker(), TokenChunker(max_tokens=512))),
        ("heading+token-256", (HeadingChunker(), TokenChunker(max_tokens=256))),
    ],
)

for result in results:
    m = result.chunking_metrics
    print(
        f"{m.chunker_name}: {m.total_chunks} chunks, "
        f"avg {m.avg_chunk_chars:.0f} chars, orphan rate {m.orphan_chunk_rate:.1%}"
    )
```
