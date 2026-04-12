#!/usr/bin/env python3
"""Demo: Incremental document sync with docprep.

Walk through a realistic workflow:
  1. Ingest a set of Markdown documents into SQLite
  2. Edit one document (add a section, modify another)
  3. Re-ingest and see that only changed chunks are flagged
  4. Export only the delta — ready for your vector store

This is the core "aha moment" for docprep: same input produces the
same chunk IDs, and when content changes, you know exactly what changed.

Usage:
    python examples/incremental_sync_demo.py
"""

from __future__ import annotations

from pathlib import Path
import tempfile

from sqlalchemy import create_engine

from docprep import ingest
from docprep.diff import compute_diff_from_documents
from docprep.export import build_export_delta, record_to_jsonl
from docprep.sinks.sqlalchemy import SQLAlchemySink

GUIDE_MD = """\
---
title: Getting Started with Acme SDK
---

# Getting Started

## Installation

Install the SDK via pip:

```bash
pip install acme-sdk
```

## Quick Start

Create a client and make your first API call:

```python
from acme import Client

client = Client(api_key="sk-...")
result = client.query("Hello, world!")
print(result.text)
```

## Configuration

Set environment variables for default configuration:

```bash
export ACME_API_KEY=sk-...
export ACME_TIMEOUT=30
```
"""

REFERENCE_MD = """\
---
title: API Reference
---

# API Reference

## Client

### `Client(api_key, timeout=30)`

Create a new API client.

**Parameters:**
- `api_key` (str): Your API key
- `timeout` (int): Request timeout in seconds

### `Client.query(prompt, model="default")`

Send a query and get a response.

**Parameters:**
- `prompt` (str): The input prompt
- `model` (str): Model identifier

**Returns:** `QueryResult` with `.text` and `.usage` attributes

## Models

Available models:
- `default` — General purpose, balanced speed/quality
- `fast` — Lower latency, slightly reduced quality
- `precise` — Highest quality, slower response
"""

# After editing: add a new section to guide and modify reference
GUIDE_MD_V2 = """\
---
title: Getting Started with Acme SDK
---

# Getting Started

## Installation

Install the SDK via pip:

```bash
pip install acme-sdk
```

## Quick Start

Create a client and make your first API call:

```python
from acme import Client

client = Client(api_key="sk-...")
result = client.query("Hello, world!")
print(result.text)
```

## Configuration

Set environment variables for default configuration:

```bash
export ACME_API_KEY=sk-...
export ACME_TIMEOUT=30
```

## Troubleshooting

### Connection Errors

If you see `ConnectionError`, check that your API key is valid
and your network allows outbound HTTPS on port 443.

### Timeout Errors

Increase the timeout for large payloads:

```python
client = Client(api_key="sk-...", timeout=120)
```
"""

REFERENCE_MD_V2 = """\
---
title: API Reference
---

# API Reference

## Client

### `Client(api_key, timeout=30, retries=3)`

Create a new API client with automatic retry support.

**Parameters:**
- `api_key` (str): Your API key
- `timeout` (int): Request timeout in seconds
- `retries` (int): Number of automatic retries on failure

### `Client.query(prompt, model="default")`

Send a query and get a response.

**Parameters:**
- `prompt` (str): The input prompt
- `model` (str): Model identifier

**Returns:** `QueryResult` with `.text` and `.usage` attributes

## Models

Available models:
- `default` — General purpose, balanced speed/quality
- `fast` — Lower latency, slightly reduced quality
- `precise` — Highest quality, slower response
- `vision` — Multimodal model with image understanding
"""


def _header(text: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {text}")
    print(f"{'─' * 60}")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()
        db_path = Path(tmpdir) / "demo.db"

        # ── Step 1: Create initial documents ──
        _header("Step 1: Create initial documents")
        (docs_dir / "guide.md").write_text(GUIDE_MD, encoding="utf-8")
        (docs_dir / "reference.md").write_text(REFERENCE_MD, encoding="utf-8")
        print("  Created: guide.md, reference.md")

        # ── Step 2: First ingestion ──
        _header("Step 2: Ingest into SQLite")
        engine = create_engine(f"sqlite:///{db_path}")
        sink = SQLAlchemySink(engine=engine, create_tables=True)
        result1 = ingest(str(docs_dir), sink=sink)

        for doc in result1.documents:
            print(f"\n  📄 {doc.title}")
            print(f"     Sections: {len(doc.sections)}")
            print(f"     Chunks:   {len(doc.chunks)}")
            for chunk in doc.chunks:
                preview = chunk.content_text[:60].replace("\n", " ")
                print(f"       [{chunk.id.hex[:8]}] {preview}...")

        total_v1 = sum(len(d.chunks) for d in result1.documents)
        print(f"\n  Total chunks: {total_v1}")

        # ── Step 3: Verify deterministic IDs ──
        _header("Step 3: Verify deterministic IDs")
        result1_again = ingest(str(docs_dir))
        ids_a = sorted(c.id.hex for d in result1.documents for c in d.chunks)
        ids_b = sorted(c.id.hex for d in result1_again.documents for c in d.chunks)
        if ids_a == ids_b:
            print("  ✅ Same input → same chunk IDs (deterministic)")
        else:
            print("  ❌ IDs differ! (this should not happen)")
            return

        # ── Step 4: Edit documents ──
        _header("Step 4: Edit documents")
        (docs_dir / "guide.md").write_text(GUIDE_MD_V2, encoding="utf-8")
        (docs_dir / "reference.md").write_text(REFERENCE_MD_V2, encoding="utf-8")
        print("  guide.md:     Added 'Troubleshooting' section")
        print("  reference.md: Added 'retries' param + 'vision' model")

        # ── Step 5: Re-ingest ──
        _header("Step 5: Re-ingest after edits")
        result2 = ingest(str(docs_dir), sink=sink)
        total_v2 = sum(len(d.chunks) for d in result2.documents)
        print(f"  Total chunks after edit: {total_v2}")

        # ── Step 6: Compute diff ──
        _header("Step 6: Compute structural diff")
        docs1 = {d.source_uri: d for d in result1.documents}
        docs2 = {d.source_uri: d for d in result2.documents}

        diffs = []
        for uri, doc2 in sorted(docs2.items()):
            doc1 = docs1.get(uri)
            diff = compute_diff_from_documents(doc1, doc2)
            diffs.append(diff)

            status_counts = {"added": 0, "modified": 0, "removed": 0, "unchanged": 0}
            for cd in diff.chunk_deltas:
                status_counts[cd.status] = status_counts.get(cd.status, 0) + 1

            filename = Path(uri).name
            parts = [f"{k}: {v}" for k, v in status_counts.items() if v > 0]
            print(f"  {filename}: {', '.join(parts)}")

        # ── Step 7: Export delta ──
        _header("Step 7: Export changed-only delta")
        delta = build_export_delta(tuple(diffs), result2.documents)

        print(f"  Added:     {len(delta.added)} records")
        print(f"  Modified:  {len(delta.modified)} records")
        print(f"  Deleted:   {len(delta.deleted_ids)} records")

        if delta.added:
            print("\n  Added records (JSONL):")
            for record in delta.added:
                print(f"    {record_to_jsonl(record)[:120]}...")

        if delta.modified:
            print("\n  Modified records (JSONL):")
            for record in delta.modified:
                print(f"    {record_to_jsonl(record)[:120]}...")

        # ── Summary ──
        _header("Summary")
        changed = len(delta.added) + len(delta.modified)
        print(f"  Total chunks:    {total_v2}")
        print(f"  Need re-embed:   {changed}")
        print(f"  Skipped:         {total_v2 - changed}")
        if total_v2 > 0:
            savings = (1 - changed / total_v2) * 100
            print(f"  Savings:         {savings:.0f}% fewer embedding API calls")
        print()
        print("  → Only changed chunks are exported.")
        print("  → Your vector store stays in sync with minimal cost.")
        print("  → Chunk IDs are stable — no orphaned vectors.")


if __name__ == "__main__":
    main()
