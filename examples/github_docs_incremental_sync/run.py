#!/usr/bin/env python3
"""Showcase incremental sync: ingest, mutate docs, compute delta export."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile

from sqlalchemy import create_engine

from docprep import RevisionDiff, build_export_delta, ingest
from docprep.diff import compute_diff_from_documents
from docprep.export import record_to_jsonl
from docprep.sinks.sqlalchemy import SQLAlchemySink

GETTING_STARTED_V1 = """---
title: Getting Started
---

# Getting Started

## Installation

Install the package and verify the CLI command is available.

```bash
pip install acme-docs
acme-docs --help
```

## Quick Start

Create a config file and run your first ingestion.

## Deployment Notes

Use staging first, then promote to production after validation.
"""

GETTING_STARTED_V2 = """---
title: Getting Started
---

# Getting Started

## Installation

Install the package, verify the CLI, and confirm Python 3.10+ is active.

```bash
pip install acme-docs
acme-docs --help
python --version
```

## Quick Start

Create a config file, run ingestion, and export changed-only records.

## Deployment Notes

Use staging first, then promote to production after validation.

## Troubleshooting

If ingestion fails, inspect parser errors and rerun after fixing source markdown.
"""

API_REFERENCE_V1 = """---
title: API Reference
---

# API Reference

## `ingest(source, sink=None)`

Ingests a source path and optionally persists documents to a sink.

### Parameters

- `source` (str): Path to documentation files.
- `sink` (Sink | None): Optional persistence target.

## `export --changed-only`

Emits only added or modified records since the previous revision.
"""

API_REFERENCE_V2 = """---
title: API Reference
---

# API Reference

## `ingest(source, sink=None, workers=1)`

Ingests a source path and optionally persists documents to a sink.

### Parameters

- `source` (str): Path to documentation files.
- `sink` (Sink | None): Optional persistence target.
- `workers` (int): Parallel workers for loading and parsing.

## `export --changed-only`

Emits only added or modified records since the previous revision.
"""

CHANGELOG_V1 = """---
title: Changelog
---

# Changelog

## 0.1.0

- Initial alpha release
- Added deterministic IDs
- Added SQLite sink
"""


def _write_initial_docs(docs_dir: Path) -> None:
    docs_dir.mkdir(parents=True, exist_ok=True)
    _ = (docs_dir / "getting-started.md").write_text(GETTING_STARTED_V1, encoding="utf-8")
    _ = (docs_dir / "api-reference.md").write_text(API_REFERENCE_V1, encoding="utf-8")
    _ = (docs_dir / "changelog.md").write_text(CHANGELOG_V1, encoding="utf-8")


def _apply_changes(docs_dir: Path) -> None:
    _ = (docs_dir / "getting-started.md").write_text(GETTING_STARTED_V2, encoding="utf-8")
    _ = (docs_dir / "api-reference.md").write_text(API_REFERENCE_V2, encoding="utf-8")
    _ = (docs_dir / "changelog.md").unlink(missing_ok=True)


def _status_counts(diff: RevisionDiff) -> dict[str, int]:
    counts = {"added": 0, "modified": 0, "removed": 0, "unchanged": 0}
    for chunk_delta in diff.chunk_deltas:
        counts[chunk_delta.status] = counts.get(chunk_delta.status, 0) + 1
    return counts


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    db_path = project_dir / "demo.db"
    delta_path = project_dir / "delta.jsonl"

    if db_path.exists():
        db_path.unlink()
    if delta_path.exists():
        delta_path.unlink()

    engine = create_engine(f"sqlite:///{db_path}")
    sink = SQLAlchemySink(engine=engine, create_tables=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs_dir = Path(tmp_dir) / "docs"
        _write_initial_docs(docs_dir)

        print("Step 1: Initial ingestion")
        result_v1 = ingest(str(docs_dir), sink=sink)
        total_v1 = sum(len(doc.chunks) for doc in result_v1.documents)
        print(f"  Ingested {len(result_v1.documents)} documents -> {total_v1} chunks")
        print(f"  Persisted to {db_path.name}")

        print("\nStep 2: Simulate document changes")
        _apply_changes(docs_dir)
        print("  Modified: getting-started.md (added Troubleshooting section)")
        print("  Modified: api-reference.md (updated parameter docs)")
        print("  Deleted:  changelog.md")

        print("\nStep 3: Re-ingest")
        result_v2 = ingest(str(docs_dir), sink=sink)
        total_v2 = sum(len(doc.chunks) for doc in result_v2.documents)
        print(f"  Ingested {len(result_v2.documents)} documents -> {total_v2} chunks")
        print(f"  Updated: {result_v2.persisted}, Skipped: {len(result_v2.skipped_source_uris)}")

        docs_v1 = {doc.source_uri: doc for doc in result_v1.documents}
        docs_v2 = {doc.source_uri: doc for doc in result_v2.documents}

        print("\nStep 4: Compute diff")
        diffs: list[RevisionDiff] = []
        for source_uri in sorted(set(docs_v1) | set(docs_v2)):
            previous = docs_v1.get(source_uri)
            current = docs_v2.get(source_uri)
            if previous is None or current is None:
                if previous is None:
                    continue
                current = replace(previous, sections=(), chunks=(), source_checksum="deleted")
            diff = compute_diff_from_documents(previous, current)
            diffs.append(diff)

            counts = _status_counts(diff)
            filename = Path(source_uri).name
            print(
                f"  {filename}: {counts['added']} added,"
                f" {counts['modified']} modified,"
                f" {counts['removed']} removed,"
                f" {counts['unchanged']} unchanged"
            )

        delta = build_export_delta(tuple(diffs), result_v2.documents)

    with delta_path.open("w", encoding="utf-8") as handle:
        for record in delta.added:
            _ = handle.write(record_to_jsonl(record) + "\n")
        for record in delta.modified:
            _ = handle.write(record_to_jsonl(record) + "\n")
        for deleted_id in delta.deleted_ids:
            _ = handle.write(json.dumps({"_deleted": True, "id": str(deleted_id)}) + "\n")

    changed_records = len(delta.added) + len(delta.modified)
    savings = (1 - (changed_records / total_v1)) * 100 if total_v1 else 0.0

    print("\nStep 5: Export delta")
    print(f"  Added: {len(delta.added)} records -> {delta_path.name}")
    print(f"  Modified: {len(delta.modified)} records -> {delta_path.name}")
    print(f"  Deleted: {len(delta.deleted_ids)} IDs (for vector store cleanup)")
    print("\n  Savings: {:.0f}% fewer embedding API calls".format(savings))
    print(f"           ({changed_records} chunks re-embedded out of {total_v1} total)")


if __name__ == "__main__":
    main()
