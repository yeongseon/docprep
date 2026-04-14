#!/usr/bin/env python3
"""Demo: MarkItDown-style document conversion to JSONL vector records."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from typing import cast

from docprep import build_vector_records_v1, ingest, iter_vector_records_v1
from docprep.export import record_to_jsonl, write_jsonl

REPORT_MD = """---
title: Q2 Platform Reliability Report
owner: SRE Team
---

# Platform Reliability Report

## Executive Summary

Overall uptime improved to 99.95% with a 42% reduction in paging alerts.

## Incidents

### API Gateway Timeout - 2026-03-17

Root cause was an exhausted connection pool during regional failover.

### Worker Queue Backlog - 2026-03-30

Batch jobs exceeded provisioned throughput and delayed downstream indexing.

## Next Actions

- Increase gateway pool sizing by 30%
- Add queue depth autoscaling policy
- Run monthly resilience game days
"""

GUIDE_MD = """---
title: Deployment Guide
owner: Platform Engineering
---

# Deployment Guide

## Prerequisites

- Python 3.10+
- Docker 24+
- Access to staging secrets

## Local Validation

Run smoke checks before opening a release PR.

```bash
make lint
make test
```

## Release Procedure

1. Merge approved PRs to `main`
2. Tag release and trigger CI pipeline
3. Verify canary metrics for 30 minutes

## Rollback

If error budget burn exceeds threshold, deploy previous stable tag.
"""


def _write_sample_docs(sample_docs_dir: Path) -> None:
    # In production, MarkItDown converts your files to Markdown first.
    # This demo uses pre-converted Markdown to avoid requiring markitdown as a dependency.
    sample_docs_dir.mkdir(parents=True, exist_ok=True)
    _ = (sample_docs_dir / "report.md").write_text(REPORT_MD, encoding="utf-8")
    _ = (sample_docs_dir / "guide.md").write_text(GUIDE_MD, encoding="utf-8")


def main() -> None:
    keep_artifacts = "--keep" in sys.argv[1:]

    project_dir = Path(__file__).resolve().parent
    sample_docs_dir = project_dir / "sample_docs"
    output_dir = project_dir / "output"
    output_path = output_dir / "records.jsonl"

    if sample_docs_dir.exists():
        shutil.rmtree(sample_docs_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)

    print("Converting sample documents...")
    _write_sample_docs(sample_docs_dir)

    result = ingest(str(sample_docs_dir))
    chunk_count = sum(len(document.chunks) for document in result.documents)

    output_dir.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        exported = write_jsonl(iter_vector_records_v1(result.documents), handle)

    records = build_vector_records_v1(result.documents)
    sample_record = (
        cast(dict[str, object], json.loads(record_to_jsonl(records[0]))) if records else {}
    )

    print(f"Ingested {len(result.documents)} documents -> {chunk_count} chunks")
    print(f"Exported {exported} records to {output_path.relative_to(project_dir)}")
    print("\nSample record:")
    print(json.dumps(sample_record, indent=2, ensure_ascii=False))

    if keep_artifacts:
        print("\nKept sample_docs/ and output/ for inspection.")
        return

    shutil.rmtree(sample_docs_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)
    print("\nCleaned up sample_docs/ and output/. Re-run with --keep to keep artifacts.")


if __name__ == "__main__":
    main()
