# Performance

This page documents docprep's performance characteristics with reproducible benchmark scenarios.

## Key Takeaway

docprep's incremental sync reduces re-embedding by **95–99%** when only a small fraction of documents change — which is the normal case for most documentation and knowledge-base corpora.

## Benchmark Environment

| Parameter | Value |
|-----------|-------|
| Python | 3.10.12 |
| Platform | Linux x86_64 |
| docprep | 0.1.1 |
| Sink | SQLite (in-memory via temp directory) |
| Chunkers | HeadingChunker → default (no token chunker) |
| Parser | Markdown (default) |

All benchmarks use synthetic Markdown corpora with realistic structure (frontmatter, headings, code blocks, tables). Results are reproducible — run the scripts yourself to verify on your hardware.

## Scenario 1: No Changes → Zero Re-exports

The baseline case: ingest a corpus, then ingest again with no changes.

| Metric | Value |
|--------|-------|
| Corpus | 100 Markdown files |
| Initial ingest | 700 chunks in 1.95s |
| Re-ingest (no changes) | 0 chunks re-exported in 0.15s |
| Savings | **100%** — nothing to re-embed |

When no files change, docprep detects identical checksums and exports zero chunks. The re-ingest runs ~13× faster than the initial ingest because the sink skips unchanged documents.

## Scenario 2: Single Typo Fix → 1 Chunk Re-exported

A single character-level edit in one file out of 100.

| Metric | Value |
|--------|-------|
| Corpus | 100 files, 700 chunks |
| Change | 1 typo fixed in 1 section of 1 file |
| Chunks re-exported | **1** out of 700 |
| Savings | **99.9%** fewer embeddings |

docprep detects that only one chunk's content hash changed and exports only that chunk. The other 699 chunks are untouched.

## Scenario 3: Heading Rename → Identity Correctly Updated

When a heading is renamed, the section anchor changes. docprep treats this as a delete + add (the old anchor is removed, the new anchor is created).

| Metric | Value |
|--------|-------|
| Corpus | 100 files |
| Change | `## Troubleshooting` → `## FAQ & Troubleshooting` in 1 file |
| Result | 1 chunk added (new anchor), 1 chunk deleted (old anchor) |

This is the expected behavior: heading-based identity means renaming a heading creates a new identity. Content under the renamed heading is re-exported under its new anchor.

## Scenario 4: Large Corpus with 5% Edits

A more realistic scenario with 500 files and 5% of them edited.

| Metric | Value |
|--------|-------|
| Corpus | 500 Markdown files |
| Initial ingest | 3,500 chunks in 13.7s |
| Change | 25 files edited (new section appended) |
| Re-ingest time | 1.28s |
| Chunks re-exported | **25** out of 3,525 |
| Savings | **99.3%** fewer embeddings |

At scale, the savings compound. With embedding costs at ~$0.0001 per call (OpenAI Ada-002), saving 3,500 calls per sync cycle adds up quickly for frequent re-ingestion workflows.

## Scenario 5: Incremental Sync End-to-End

From the included `examples/benchmark_incremental_sync.py`:

| Metric | Value |
|--------|-------|
| Corpus | 50 files (~100 lines each) |
| Edit fraction | 10% (5 files) |
| Initial ingest | 350 chunks in 1.07s |
| Chunks after edit | 360 (10 new chunks from added sections) |
| Re-export | **10 chunks** (all added, 0 modified) |
| Savings | **97.2%** fewer embeddings |
| Deterministic IDs | ✅ 350 chunk IDs identical across runs |

## Concurrency

docprep supports multi-threaded parsing and chunking via the `workers` parameter.

| Workers | 100 files | Notes |
|---------|-----------|-------|
| 1 | 0.030s | Single-threaded baseline |
| 2 | 0.031s | Minimal speedup (I/O bound at this scale) |
| 4 | 0.036s | Thread overhead > benefit for small corpora |
| 8 | 0.040s | Thread overhead dominates |

For small corpora (< 500 files), single-threaded ingestion is fastest due to thread pool overhead. Multi-threading benefits appear with larger corpora or when using heavier parsers (HTML, RST) where parse time dominates.

```python
from docprep import ingest

# Single-threaded (best for < 500 files)
result = ingest("docs/")

# Multi-threaded (useful for large corpora)
result = ingest("docs/", workers=4)
```

## Cost Estimation

For a typical documentation corpus with daily re-ingestion:

| Corpus Size | Daily Edits | Naive Re-embed | docprep Re-embed | Monthly Savings (Ada-002) |
|-------------|-------------|----------------|-------------------|---------------------------|
| 100 files | 5% | 700 chunks | ~5 chunks | $0.63 |
| 1,000 files | 3% | 7,000 chunks | ~30 chunks | $6.27 |
| 10,000 files | 1% | 70,000 chunks | ~100 chunks | $62.73 |

*Assumes ~7 chunks/file average, $0.0001/embedding (Ada-002), 30 days/month.*

The cost savings scale linearly with corpus size and inversely with edit frequency. For enterprise-scale corpora with thousands of documents and infrequent changes, incremental sync can reduce embedding costs by over 99%.

## Reproducing These Results

### Incremental sync benchmark

```bash
python examples/benchmark_incremental_sync.py
```

### Concurrency benchmark

```bash
python benchmarks/bench_concurrency.py --docs 100
```

### Custom scenarios

```python
from docprep import ingest
from docprep.diff import compute_diff_from_documents
from docprep.export import build_export_delta

# Ingest, edit files, ingest again, then diff
result_before = ingest("docs/")
# ... edit some files ...
result_after = ingest("docs/")

diffs = []
before_map = {d.source_uri: d for d in result_before.documents}
for doc in result_after.documents:
    prev = before_map.get(doc.source_uri)
    diffs.append(compute_diff_from_documents(prev, doc))

delta = build_export_delta(tuple(diffs), result_after.documents)
print(f"Re-embed: {len(delta.added) + len(delta.modified)} chunks")
print(f"Delete:   {len(delta.deleted_ids)} chunks")
```
