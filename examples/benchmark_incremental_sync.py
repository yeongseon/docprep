#!/usr/bin/env python3
"""Benchmark: How much re-embedding does docprep's incremental sync save?

This script demonstrates docprep's core value proposition:
when documents change, you only re-embed the chunks that actually changed.

It creates a realistic corpus, ingests it, simulates edits to a fraction
of files, re-ingests, and measures exactly how many chunks need re-embedding
versus a naive "re-embed everything" approach.

Usage:
    python examples/benchmark_incremental_sync.py
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import time

from sqlalchemy import create_engine

from docprep import ingest
from docprep.diff import compute_diff_from_documents
from docprep.export import build_export_delta
from docprep.sinks.sqlalchemy import SQLAlchemySink


def _create_corpus(base_dir: Path, num_files: int = 50) -> None:
    """Generate a synthetic Markdown corpus with realistic structure."""
    for i in range(num_files):
        content = f"""---
title: Document {i:03d} — API Reference
author: engineering-team
tags: [api, reference, v2]
---

# Document {i:03d}: API Reference

## Overview

This document describes the API for module {i:03d}. The module provides
core functionality for data processing and transformation pipelines.
It supports both synchronous and asynchronous execution modes.

## Authentication

All API calls require a valid bearer token. Tokens are issued by the
identity service and must be refreshed every 3600 seconds.

```python
import httpx

client = httpx.Client(headers={{"Authorization": "Bearer {{token}}"}})
response = client.get("/api/v2/module-{i:03d}/status")
```

## Endpoints

### GET /api/v2/module-{i:03d}/status

Returns the current status of the module including health checks,
active connections, and throughput metrics.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| verbose | bool | No | Include detailed metrics |
| format | string | No | Response format (json, yaml) |

### POST /api/v2/module-{i:03d}/process

Submit a batch of items for processing. Items are queued and processed
in FIFO order with configurable concurrency limits.

**Request body:**

```json
{{
  "items": ["item-1", "item-2"],
  "options": {{
    "concurrency": 4,
    "timeout_seconds": 30
  }}
}}
```

## Error Handling

The API uses standard HTTP status codes. All error responses include
a machine-readable error code and human-readable message.

| Status | Code | Description |
|--------|------|-------------|
| 400 | INVALID_REQUEST | Malformed request body |
| 401 | UNAUTHORIZED | Missing or expired token |
| 429 | RATE_LIMITED | Too many requests |
| 500 | INTERNAL_ERROR | Server-side failure |

## Rate Limits

Default rate limits are 100 requests per minute per token.
Enterprise plans support custom limits up to 10,000 req/min.

## Changelog

- v2.1.0: Added batch processing endpoint
- v2.0.0: Initial v2 release with breaking changes
- v1.3.0: Added rate limiting headers
"""
        (base_dir / f"doc-{i:03d}.md").write_text(content, encoding="utf-8")


def _simulate_edits(base_dir: Path, edit_fraction: float = 0.10) -> list[str]:
    """Edit a fraction of files to simulate real-world document updates."""
    files = sorted(base_dir.glob("*.md"))
    num_to_edit = max(1, int(len(files) * edit_fraction))
    edited = []

    for f in files[:num_to_edit]:
        original = f.read_text(encoding="utf-8")
        # Append a new section — simulating a real documentation update
        updated = (
            original
            + """
## Migration Guide

To migrate from v1 to v2, update your base URL from `/api/v1/` to `/api/v2/`
and refresh your authentication tokens. The response format for batch
endpoints has changed — see the updated schema above.

### Breaking Changes

1. Authentication tokens are now required for all endpoints
2. Batch responses include a `job_id` field for async tracking
3. Rate limit headers use `X-RateLimit-*` prefix (was `RateLimit-*`)
"""
        )
        f.write_text(updated, encoding="utf-8")
        edited.append(f.name)

    return edited


def main() -> None:
    num_files = 50
    edit_fraction = 0.10  # Edit 10% of files

    with tempfile.TemporaryDirectory() as tmpdir:
        corpus_dir = Path(tmpdir) / "corpus"
        corpus_dir.mkdir()
        db_path = Path(tmpdir) / "benchmark.db"

        # --- Phase 1: Initial ingestion ---
        print("=" * 70)
        print("docprep Incremental Sync Benchmark")
        print("=" * 70)
        print(f"\nCorpus: {num_files} Markdown files (~100 lines each)")
        print(f"Edit fraction: {edit_fraction:.0%} of files modified\n")

        _create_corpus(corpus_dir, num_files)

        engine = create_engine(f"sqlite:///{db_path}")
        sink = SQLAlchemySink(engine=engine, create_tables=True)

        t0 = time.perf_counter()
        result1 = ingest(str(corpus_dir), sink=sink)
        t1 = time.perf_counter()

        total_chunks_v1 = sum(len(d.chunks) for d in result1.documents)
        total_sections_v1 = sum(len(d.sections) for d in result1.documents)

        print("--- Phase 1: Initial Ingestion ---")
        print(f"  Documents:  {len(result1.documents)}")
        print(f"  Sections:   {total_sections_v1}")
        print(f"  Chunks:     {total_chunks_v1}")
        print(f"  Time:       {t1 - t0:.2f}s")

        # Verify deterministic IDs: re-ingest same content, IDs must match
        result1_verify = ingest(str(corpus_dir))
        ids_v1 = {c.id for d in result1.documents for c in d.chunks}
        ids_v1_verify = {c.id for d in result1_verify.documents for c in d.chunks}
        assert ids_v1 == ids_v1_verify, "Deterministic ID invariant violated!"
        print(f"  ID check:   ✅ {len(ids_v1)} chunk IDs identical across runs")

        # --- Phase 2: Edit subset and re-ingest ---
        edited_files = _simulate_edits(corpus_dir, edit_fraction)
        num_edited = len(edited_files)

        t2 = time.perf_counter()
        result2 = ingest(str(corpus_dir), sink=sink)
        t3 = time.perf_counter()

        total_chunks_v2 = sum(len(d.chunks) for d in result2.documents)

        print(f"\n--- Phase 2: After Editing {num_edited} Files ---")
        print(f"  Re-ingest:  {t3 - t2:.2f}s")
        print(f"  Chunks:     {total_chunks_v2}")

        # --- Phase 3: Compute diff / export delta ---
        docs1_by_uri = {d.source_uri: d for d in result1.documents}
        docs2_by_uri = {d.source_uri: d for d in result2.documents}

        diffs = []
        for uri, doc2 in docs2_by_uri.items():
            doc1 = docs1_by_uri.get(uri)
            diff = compute_diff_from_documents(doc1, doc2)
            diffs.append(diff)

        delta = build_export_delta(tuple(diffs), result2.documents)

        chunks_to_reembed = len(delta.added) + len(delta.modified)
        chunks_to_delete = len(delta.deleted_ids)
        chunks_unchanged = total_chunks_v2 - chunks_to_reembed

        print("\n--- Phase 3: Incremental Sync Results ---")
        print(f"  Added chunks:     {len(delta.added)}")
        print(f"  Modified chunks:  {len(delta.modified)}")
        print(f"  Deleted chunks:   {chunks_to_delete}")
        print(f"  Unchanged chunks: {chunks_unchanged}")

        # --- Summary ---
        naive_reembed = total_chunks_v2
        smart_reembed = chunks_to_reembed
        savings_pct = (1 - smart_reembed / naive_reembed) * 100 if naive_reembed else 0

        print(f"\n{'=' * 70}")
        print("RESULTS SUMMARY")
        print(f"{'=' * 70}")
        print(f"  Naive approach:  re-embed ALL {naive_reembed} chunks")
        print(f"  docprep:         re-embed only {smart_reembed} chunks")
        print(f"  Savings:         {savings_pct:.1f}% fewer embeddings")
        print(f"  Cost reduction:  {naive_reembed - smart_reembed} embedding API calls saved")
        print()
        print(f"  With 10% file edits, docprep reduces re-embedding by ~{savings_pct:.0f}%.")
        print(f"  At $0.0001/embedding (Ada-002), saving {naive_reembed - smart_reembed} calls")
        print(f"  saves ${(naive_reembed - smart_reembed) * 0.0001:.4f} per sync cycle.")
        print("  For larger corpora (10k+ docs), this compounds significantly.")
        print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
