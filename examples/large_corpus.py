#!/usr/bin/env python3
"""Example: Processing a large document corpus with docprep.

Demonstrates patterns for handling large corpora:
  1. Parallel ingestion with workers
  2. Resumable ingestion with checkpoints
  3. Database persistence for incremental updates
  4. Progress monitoring
  5. Memory-efficient iteration

Usage:
    python examples/large_corpus.py
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import time

from sqlalchemy import create_engine

from docprep import (
    IngestProgressEvent,
    ingest,
    iter_vector_records_v1,
)
from docprep.export import write_jsonl
from docprep.sinks.sqlalchemy import SQLAlchemySink

# ---------------------------------------------------------------------------
# Corpus generator
# ---------------------------------------------------------------------------


def generate_corpus(base_dir: Path, num_files: int = 200) -> None:
    """Generate a synthetic Markdown corpus for testing."""
    categories = ["api", "guide", "tutorial", "reference", "faq"]
    for i in range(num_files):
        category = categories[i % len(categories)]
        content = f"""---
title: "{category.title()} Document {i:04d}"
category: {category}
version: "1.0"
---

# {category.title()} Document {i:04d}

## Overview

This is document {i:04d} in the {category} category.
It demonstrates how docprep handles large corpora with many files.

## Section A

Content for section A of document {i:04d}. This section covers
the primary functionality and core concepts that users need
to understand before proceeding.

### Subsection A.1

Detailed information about the first aspect of section A.
This includes code examples, configuration options, and
common patterns.

```python
def process_{category}_{i:04d}(data):
    \"\"\"Process data for {category} {i:04d}.\"\"\"
    return transform(data, mode="{category}")
```

### Subsection A.2

Additional details and edge cases for section A. These are
important for production deployments.

## Section B

Secondary content covering advanced topics, integration
patterns, and troubleshooting guidance.

| Setting | Default | Description |
|---------|---------|-------------|
| timeout | 30s | Request timeout |
| retries | 3 | Number of retries |
| batch_size | 100 | Items per batch |
"""
        (base_dir / f"{category}-{i:04d}.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Pattern 1: Parallel ingestion
# ---------------------------------------------------------------------------


def demo_parallel_ingestion(docs_dir: Path) -> None:
    """Use multiple workers for faster ingestion."""
    print("── Pattern 1: Parallel Ingestion ──\n")

    # Single worker (sequential)
    t0 = time.perf_counter()
    result_seq = ingest(str(docs_dir), workers=1)
    t_seq = time.perf_counter() - t0

    # Multiple workers (parallel parse + chunk)
    t0 = time.perf_counter()
    result_par = ingest(str(docs_dir), workers=4)
    t_par = time.perf_counter() - t0

    print(f"  Sequential (1 worker):  {t_seq:.2f}s — {len(result_seq.documents)} docs")
    print(f"  Parallel   (4 workers): {t_par:.2f}s — {len(result_par.documents)} docs")
    if t_seq > 0:
        speedup = t_seq / t_par if t_par > 0 else float("inf")
        print(f"  Speedup: {speedup:.1f}x")
    print()


# ---------------------------------------------------------------------------
# Pattern 2: Resumable ingestion
# ---------------------------------------------------------------------------


def demo_resumable_ingestion(docs_dir: Path, tmpdir: Path) -> None:
    """Resume interrupted ingestion from a checkpoint."""
    print("── Pattern 2: Resumable Ingestion ──\n")

    checkpoint_path = tmpdir / "checkpoint.json"

    # First run: process everything
    result1 = ingest(
        str(docs_dir),
        resume=True,
        checkpoint_path=str(checkpoint_path),
    )
    print(f"  First run:  {result1.processed_count} processed")

    # Second run: checkpoint skips already-processed files
    result2 = ingest(
        str(docs_dir),
        resume=True,
        checkpoint_path=str(checkpoint_path),
    )
    print(f"  Second run: {result2.processed_count} processed, {result2.skipped_count} skipped")

    print(f"  Checkpoint file: {checkpoint_path.name} (auto-managed by docprep)")


# ---------------------------------------------------------------------------
# Pattern 3: Database persistence for incremental updates
# ---------------------------------------------------------------------------


def demo_incremental_with_db(docs_dir: Path, tmpdir: Path) -> None:
    """Use SQLite persistence for incremental ingestion."""
    print("── Pattern 3: Database Persistence ──\n")

    db_path = tmpdir / "corpus.db"
    engine = create_engine(f"sqlite:///{db_path}")
    sink = SQLAlchemySink(engine=engine, create_tables=True)

    # Initial ingestion
    t0 = time.perf_counter()
    result1 = ingest(str(docs_dir), sink=sink)
    t1 = time.perf_counter()

    print(f"  Initial:  {result1.processed_count} docs in {t1 - t0:.2f}s")
    print(f"  Persisted: {result1.persisted}")

    # Re-ingest without changes — should detect no changes
    t0 = time.perf_counter()
    result2 = ingest(str(docs_dir), sink=sink)
    t2 = time.perf_counter()

    print(
        f"  Re-ingest: {result2.processed_count} processed, "
        f"{result2.skipped_count} skipped in {t2 - t0:.2f}s"
    )

    # Modify one file and re-ingest
    first_file = sorted(docs_dir.glob("*.md"))[0]
    original = first_file.read_text(encoding="utf-8")
    first_file.write_text(original + "\n## Added Section\n\nNew content here.\n", encoding="utf-8")

    t0 = time.perf_counter()
    result3 = ingest(str(docs_dir), sink=sink)
    t3 = time.perf_counter()

    print(
        f"  After edit: {result3.updated_count} updated, "
        f"{result3.skipped_count} skipped in {t3 - t0:.2f}s"
    )

    # Restore the file
    first_file.write_text(original, encoding="utf-8")
    print()


# ---------------------------------------------------------------------------
# Pattern 4: Progress monitoring
# ---------------------------------------------------------------------------


def demo_progress_monitoring(docs_dir: Path) -> None:
    """Track progress during large corpus ingestion."""
    print("── Pattern 4: Progress Monitoring ──\n")

    completed = 0
    total_files = 0

    def on_progress(event: IngestProgressEvent) -> None:
        nonlocal completed, total_files
        if event.total is not None:
            total_files = event.total
        if event.event == "complete" and event.source_uri:
            completed += 1
            if completed % 50 == 0 or completed == total_files:
                print(f"  Progress: {completed}/{total_files} files processed")

    result = ingest(str(docs_dir), progress_callback=on_progress)

    # Stage timing
    if result.stage_reports:
        print("\n  Stage timings:")
        for report in result.stage_reports:
            print(
                f"    {report.stage}: "
                f"{report.elapsed_ms:.0f}ms "
                f"({report.input_count}→{report.output_count})"
            )
    print()


# ---------------------------------------------------------------------------
# Pattern 5: Memory-efficient export
# ---------------------------------------------------------------------------


def demo_streaming_export(docs_dir: Path, tmpdir: Path) -> None:
    """Stream records to JSONL without loading all into memory."""
    print("── Pattern 5: Memory-Efficient Export ──\n")

    result = ingest(str(docs_dir))

    jsonl_path = tmpdir / "corpus.jsonl"

    # iter_vector_records_v1 is a lazy iterator — constant memory
    with open(jsonl_path, "w", encoding="utf-8") as f:
        count = write_jsonl(iter_vector_records_v1(result.documents), f)

    file_size = jsonl_path.stat().st_size
    print(f"  Exported {count} records to {jsonl_path.name}")
    print(f"  File size: {file_size / 1024:.1f} KB")
    print(f"  Average: {file_size / count:.0f} bytes/record")
    print()


def main() -> None:
    num_files = 200

    print("=" * 60)
    print("  docprep Large Corpus Examples")
    print(f"  Corpus: {num_files} synthetic Markdown files")
    print("=" * 60)
    print()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        docs_dir = tmpdir_path / "corpus"
        docs_dir.mkdir()

        print(f"Generating {num_files} files...")
        generate_corpus(docs_dir, num_files)
        total_size = sum(f.stat().st_size for f in docs_dir.glob("*.md"))
        print(f"Corpus size: {total_size / 1024:.0f} KB\n")

        demo_parallel_ingestion(docs_dir)
        demo_resumable_ingestion(docs_dir, tmpdir_path)
        demo_incremental_with_db(docs_dir, tmpdir_path)
        demo_progress_monitoring(docs_dir)
        demo_streaming_export(docs_dir, tmpdir_path)

    print("=" * 60)
    print("  Key takeaways:")
    print("  • Use workers=N for parallel parse+chunk")
    print("  • Use resume=True for large/flaky ingestion pipelines")
    print("  • Use a sink for incremental updates (skip unchanged files)")
    print("  • Use iter_vector_records_v1() for memory-efficient export")
    print("  • Use progress_callback for monitoring")
    print("=" * 60)


if __name__ == "__main__":
    main()
