# GitHub Docs Incremental Sync

Demonstrate docprep's core value: ingest a set of documents, make changes, re-ingest, and export only the delta.

## What This Example Does

1. Creates a set of documentation files (simulating a project's docs/)
2. Ingests them into SQLite with full revision tracking
3. Simulates document edits (add a section, modify content, delete a file)
4. Re-ingests and computes a structural diff
5. Exports only the changed chunks as JSONL - ready for your vector store

## Prerequisites

- Python 3.10+

## Setup

```bash
cd examples/github_docs_incremental_sync
pip install -r requirements.txt
```

## Run

```bash
python run.py
```

## Expected Output

```
Step 1: Initial ingestion
  Ingested 3 documents -> 15 chunks
  Persisted to demo.db

Step 2: Simulate document changes
  Modified: getting-started.md (added Troubleshooting section)
  Modified: api-reference.md (updated parameter docs)
  Deleted:  changelog.md

Step 3: Re-ingest
  Ingested 2 documents -> 13 chunks
  Updated: 2, Skipped: 0

Step 4: Compute diff
  getting-started.md: 2 added, 1 modified, 0 removed, 4 unchanged
  api-reference.md: 0 added, 2 modified, 0 removed, 3 unchanged
  changelog.md: 0 added, 0 modified, 5 removed, 0 unchanged

Step 5: Export delta
  Added: 2 records -> delta.jsonl
  Modified: 3 records -> delta.jsonl
  Deleted: 5 IDs (for vector store cleanup)

  Savings: 67% fewer embedding API calls
           (5 chunks re-embedded out of 15 total)
```

## What to Try Next

- Point the script at your own docs directory
- Connect to PostgreSQL instead of SQLite for production use
- Pipe delta.jsonl to your vector store's bulk import
