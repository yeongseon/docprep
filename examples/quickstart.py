#!/usr/bin/env python3
"""Quickstart: The simplest possible docprep example.

Ingest a directory of Markdown files and print the results.
This is your "Hello World" for docprep.

Usage:
    python examples/quickstart.py

    # Or point at your own docs:
    python examples/quickstart.py /path/to/your/docs
"""

from __future__ import annotations

from pathlib import Path
import sys

from docprep import ingest


def main() -> None:
    # Use command-line argument or the bundled sample docs
    source = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent / "sample_docs")

    # One line to ingest everything
    result = ingest(source)

    # Print what we got
    print(f"Ingested {len(result.documents)} documents:\n")
    for doc in result.documents:
        print(f"  {doc.title}")
        print(f"    Source:   {doc.source_uri}")
        print(f"    Sections: {len(doc.sections)}")
        print(f"    Chunks:   {len(doc.chunks)}")
        print()

    # Show total chunks
    total = sum(len(d.chunks) for d in result.documents)
    print(f"Total: {total} chunks ready for embedding")


if __name__ == "__main__":
    main()
