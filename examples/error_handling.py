#!/usr/bin/env python3
"""Example: Error handling patterns in docprep.

Demonstrates how to handle errors gracefully during document ingestion:
  1. ErrorMode.CONTINUE_ON_ERROR — skip failures, collect errors
  2. ErrorMode.FAIL_FAST — stop on first failure
  3. Progress callbacks — monitor ingestion in real time
  4. Individual error inspection

Usage:
    python examples/error_handling.py
"""

from __future__ import annotations

from pathlib import Path
import tempfile

from docprep import (
    ChunkError,
    ConfigError,
    DocPrepError,
    ErrorMode,
    IngestError,
    IngestProgressEvent,
    LoadError,
    ParseError,
    SinkError,
    ingest,
)

# ---------------------------------------------------------------------------
# Sample data: mix of valid and problematic files
# ---------------------------------------------------------------------------

VALID_MD = """\
---
title: Valid Document
---

# Valid Document

This document is perfectly valid and will be processed without issues.

## Section One

Some content in section one.

## Section Two

Some content in section two.
"""

# A file with unusual encoding (will work but shows robustness)
EMPTY_MD = ""

# Binary content that looks like markdown but isn't well-formed
WEIRD_MD = """\
# Document with Edge Cases

## Empty section below

## Section with only whitespace

   

## Normal section

This section has actual content.
"""


def demo_continue_on_error() -> None:
    """Pattern 1: Continue processing even when some files fail."""
    print("── Pattern 1: CONTINUE_ON_ERROR (default) ──\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()

        # Create a mix of files
        (docs_dir / "valid.md").write_text(VALID_MD, encoding="utf-8")
        (docs_dir / "empty.md").write_text(EMPTY_MD, encoding="utf-8")
        (docs_dir / "edge_cases.md").write_text(WEIRD_MD, encoding="utf-8")

        # Default mode: continue on error
        result = ingest(str(docs_dir), error_mode=ErrorMode.CONTINUE_ON_ERROR)

        print(f"  Processed:  {result.processed_count}")
        print(f"  Skipped:    {result.skipped_count}")
        print(f"  Failed:     {result.failed_count}")
        print(f"  Documents:  {len(result.documents)}")

        if result.errors:
            print(f"\n  Errors ({len(result.errors)}):")
            for error in result.errors:
                print(f"    [{error.stage}] {error.source_uri}: {error.message}")
        else:
            print("\n  No errors (all files processed successfully)")

        if result.failed_source_uris:
            print(f"\n  Failed URIs: {result.failed_source_uris}")

    print()


def demo_fail_fast() -> None:
    """Pattern 2: Stop immediately on first failure."""
    print("── Pattern 2: FAIL_FAST ──\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()

        (docs_dir / "valid.md").write_text(VALID_MD, encoding="utf-8")

        try:
            result = ingest(str(docs_dir), error_mode=ErrorMode.FAIL_FAST)
            print(f"  Success! Processed {result.processed_count} documents")
        except DocPrepError as exc:
            print(f"  Caught {type(exc).__name__}: {exc}")
            print("  Pipeline stopped at first failure")

    print()


def demo_progress_callback() -> None:
    """Pattern 3: Monitor ingestion progress in real time."""
    print("── Pattern 3: Progress Callbacks ──\n")

    events: list[str] = []

    def on_progress(event: IngestProgressEvent) -> None:
        msg = f"  [{event.stage}] {event.event}"
        if event.source_uri:
            msg += f" — {Path(event.source_uri).name}"
        if event.current is not None and event.total is not None:
            msg += f" ({event.current}/{event.total})"
        events.append(msg)

    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()

        (docs_dir / "doc1.md").write_text(VALID_MD, encoding="utf-8")
        (docs_dir / "doc2.md").write_text(WEIRD_MD, encoding="utf-8")

        result = ingest(str(docs_dir), progress_callback=on_progress)

        for event_msg in events:
            print(event_msg)

        print(f"\n  Total events: {len(events)}")
        print(f"  Documents processed: {result.processed_count}")

    print()


def demo_exception_hierarchy() -> None:
    """Pattern 4: Understanding the exception hierarchy."""
    print("── Pattern 4: Exception Hierarchy ──\n")

    print("  DocPrepError (base)")
    print("  ├── ConfigError     — invalid configuration")
    print("  ├── LoadError       — file loading failed")
    print("  ├── ParseError      — document parsing failed")
    print("  ├── ChunkError      — chunking failed")
    print("  ├── IngestError     — pipeline orchestration error")
    print("  ├── SinkError       — persistence/database error")
    print("  └── MetadataError   — metadata validation error")
    print()
    print("  Usage pattern:")
    print()
    print("    try:")
    print('        result = ingest("docs/")')
    print("    except ConfigError:")
    print("        # Fix your docprep.toml")
    print("    except LoadError:")
    print("        # File not found, permission denied, encoding error")
    print("    except ParseError:")
    print("        # Malformed document content")
    print("    except SinkError:")
    print("        # Database connection failed")
    print("    except DocPrepError:")
    print("        # Catch-all for any docprep error")
    print()

    # Verify the hierarchy
    assert issubclass(ConfigError, DocPrepError)
    assert issubclass(LoadError, DocPrepError)
    assert issubclass(ParseError, DocPrepError)
    assert issubclass(ChunkError, DocPrepError)
    assert issubclass(IngestError, DocPrepError)
    assert issubclass(SinkError, DocPrepError)
    print("  ✅ All error classes inherit from DocPrepError")
    print()


def demo_stage_reports() -> None:
    """Pattern 5: Inspect per-stage timing."""
    print("── Pattern 5: Stage Reports ──\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        docs_dir = Path(tmpdir) / "docs"
        docs_dir.mkdir()

        (docs_dir / "doc.md").write_text(VALID_MD, encoding="utf-8")

        result = ingest(str(docs_dir))

        if result.stage_reports:
            for report in result.stage_reports:
                print(
                    f"  {report.stage}: "
                    f"{report.elapsed_ms:.1f}ms, "
                    f"{report.input_count} in → {report.output_count} out"
                )
        else:
            print("  (No stage reports — single-file ingestion)")

    print()


def main() -> None:
    print("=" * 60)
    print("  docprep Error Handling Examples")
    print("=" * 60)
    print()

    demo_continue_on_error()
    demo_fail_fast()
    demo_progress_callback()
    demo_exception_hierarchy()
    demo_stage_reports()

    print("=" * 60)
    print("  Key takeaways:")
    print("  • Use CONTINUE_ON_ERROR (default) for batch processing")
    print("  • Use FAIL_FAST for CI/CD pipelines")
    print("  • Use progress callbacks for monitoring")
    print("  • Catch DocPrepError for generic handling")
    print("  • Check result.errors for per-file failure details")
    print("=" * 60)


if __name__ == "__main__":
    main()
