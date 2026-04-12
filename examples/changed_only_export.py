"""Example: Export only chunks that changed since the last ingestion run."""

from __future__ import annotations

import sys

from sqlalchemy import create_engine

from docprep import ingest
from docprep.diff import compute_diff_from_documents
from docprep.export import build_export_delta, record_to_jsonl
from docprep.sinks.sqlalchemy import SQLAlchemySink


def main() -> None:
    engine = create_engine("sqlite:///docs.db")
    sink = SQLAlchemySink(engine=engine, create_tables=True)

    # Ingest (persists to DB and returns current documents)
    result = ingest("docs/", sink=sink)

    # Compute diffs against previously stored versions
    diffs = []
    for doc in result.documents:
        previous = sink.get_document(doc.source_uri)
        diff = compute_diff_from_documents(previous, doc)
        diffs.append(diff)

    # Build export delta (only added/modified/deleted)
    delta = build_export_delta(tuple(diffs), result.documents)

    # Write added/modified records as JSONL
    for record in delta.added + delta.modified:
        print(record_to_jsonl(record))

    # Write deleted IDs for downstream cleanup
    for deleted_id in delta.deleted_ids:
        print(f'{{"_deleted": true, "id": "{deleted_id}"}}')

    # Summary to stderr
    print(
        f"Delta: {len(delta.added)} added, {len(delta.modified)} modified, "
        f"{len(delta.deleted_ids)} deleted",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
