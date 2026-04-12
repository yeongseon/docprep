#!/usr/bin/env python3
"""Example: Write a custom adapter for an external document converter.

An adapter converts external tool output (e.g., MarkItDown, Docling)
into docprep Documents. This example shows two patterns:

  1. A simple adapter that wraps MarkItDown (requires `pip install markitdown`)
  2. A minimal custom adapter from scratch (no external dependencies)

Usage:
    python examples/adapter_markitdown.py
"""

from __future__ import annotations

from collections.abc import Iterable
import csv
from pathlib import Path
import tempfile

from docprep import Adapter, Document, ingest

# ---------------------------------------------------------------------------
# Pattern 1: Wrapping MarkItDown (when you have it installed)
# ---------------------------------------------------------------------------


class MarkItDownAdapter:
    """Adapter that uses Microsoft MarkItDown to convert files to Markdown.

    Install: pip install markitdown

    MarkItDown supports: PDF, DOCX, PPTX, XLSX, HTML, images, and more.
    This adapter converts them to Markdown, then lets docprep handle
    chunking and ID generation.
    """

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".pdf", ".docx", ".pptx", ".xlsx", ".html"})

    def convert(self, source: str | Path) -> Iterable[Document]:
        # This would use the real MarkItDown library:
        #
        #   from markitdown import MarkItDown
        #   md = MarkItDown()
        #   result = md.convert(str(source))
        #   markdown_text = result.text_content
        #
        # Then feed the markdown into docprep's ingest:
        #   result = ingest(source_text=markdown_text)
        #   return result.documents
        #
        # For this example, we simulate the conversion:
        raise NotImplementedError(
            "Install markitdown (`pip install markitdown`) to use this adapter. "
            "See the commented code above for the real implementation."
        )


# ---------------------------------------------------------------------------
# Pattern 2: Minimal custom adapter (no dependencies)
# ---------------------------------------------------------------------------


class CsvToMarkdownAdapter:
    """Converts CSV files to Markdown tables for docprep ingestion.

    This demonstrates writing a custom adapter from scratch.
    The adapter reads CSV files and converts each one to a Markdown
    document with the data rendered as a table.
    """

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".csv"})

    def convert(self, source: str | Path) -> Iterable[Document]:
        source_path = Path(source)

        if source_path.is_file():
            files = [source_path]
        else:
            files = sorted(source_path.glob("**/*.csv"))

        for csv_file in files:
            markdown = self._csv_to_markdown(csv_file)

            # Write temporary markdown and ingest it
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(markdown)
                tmp_path = tmp.name

            result = ingest(tmp_path)
            yield from result.documents

            Path(tmp_path).unlink()

    @staticmethod
    def _csv_to_markdown(csv_file: Path) -> str:
        """Convert a CSV file to a Markdown document with a table."""
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            return f"# {csv_file.stem}\n\nEmpty file.\n"

        title = csv_file.stem.replace("_", " ").replace("-", " ").title()
        lines = [f"# {title}\n"]

        # Header row
        header = rows[0]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")

        # Data rows
        for row in rows[1:]:
            # Pad row to match header length
            padded = row + [""] * (len(header) - len(row))
            lines.append("| " + " | ".join(padded[: len(header)]) + " |")

        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Demo: Use the CSV adapter
# ---------------------------------------------------------------------------


def main() -> None:
    print("docprep Adapter Example")
    print("=" * 50)

    # Create a sample CSV file
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "team.csv"
        csv_path.write_text(
            "Name,Role,Department\n"
            "Alice,Engineer,Platform\n"
            "Bob,Designer,Product\n"
            "Carol,Manager,Engineering\n"
            "Dave,Analyst,Data\n",
            encoding="utf-8",
        )

        print(f"\nCSV file: {csv_path.name}")
        print(f"Content:\n{csv_path.read_text()}")

        # Use the adapter
        adapter = CsvToMarkdownAdapter()
        documents = list(adapter.convert(tmpdir))

        print(f"Converted to {len(documents)} document(s):\n")
        for doc in documents:
            print(f"  Title: {doc.title}")
            print(f"  Chunks: {len(doc.chunks)}")
            for chunk in doc.chunks:
                preview = chunk.content_text[:80].replace("\n", " ")
                print(f"    [{chunk.id.hex[:8]}] {preview}...")
            print()

    # Show the adapter protocol
    print("Adapter Protocol")
    print("-" * 50)
    print("To create your own adapter, implement two methods:")
    print()
    print("  class MyAdapter:")
    print("      @property")
    print("      def supported_extensions(self) -> frozenset[str]:")
    print('          return frozenset({".pdf", ".docx"})')
    print()
    print("      def convert(self, source) -> Iterable[Document]:")
    print("          # Convert source file(s) to docprep Documents")
    print("          ...")
    print()
    print("Then pass your Markdown output to docprep's ingest().")

    # Verify it satisfies the protocol
    assert isinstance(CsvToMarkdownAdapter(), Adapter), "Must satisfy Adapter protocol"
    print("\n✅ CsvToMarkdownAdapter satisfies the Adapter protocol")


if __name__ == "__main__":
    main()
