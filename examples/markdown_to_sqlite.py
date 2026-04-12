"""Example: Ingest Markdown documents into SQLite and query the results."""

from __future__ import annotations

from sqlalchemy import create_engine

from docprep import ingest
from docprep.export import iter_vector_records_v1, write_jsonl
from docprep.sinks.sqlalchemy import SQLAlchemySink


def main() -> None:
    # 1. Set up the database
    engine = create_engine("sqlite:///docs.db")
    sink = SQLAlchemySink(engine=engine, create_tables=True)

    # 2. Ingest documents
    result = ingest("docs/", sink=sink)
    print(f"Documents: {len(result.documents)}")
    print(f"Persisted: {result.persisted}")
    print(f"Skipped (unchanged): {len(result.skipped_source_uris)}")

    # 3. Print document summaries
    for doc in result.documents:
        print(f"\n  {doc.title}")
        print(f"    Sections: {len(doc.sections)}")
        print(f"    Chunks: {len(doc.chunks)}")

    # 4. Export to JSONL
    with open("records.jsonl", "w") as f:
        count = write_jsonl(iter_vector_records_v1(result.documents), f)
    print(f"\nExported {count} records to records.jsonl")


if __name__ == "__main__":
    main()
