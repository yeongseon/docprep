# MarkItDown to JSONL

Convert documents (PDF, DOCX, PPTX, etc.) to structured JSONL using [MarkItDown](https://github.com/microsoft/markitdown) and docprep.

## What This Example Does

1. Converts sample documents to Markdown via MarkItDown
2. Ingests the Markdown through docprep's chunking pipeline
3. Exports structured `VectorRecordV1` records as JSONL

## Prerequisites

- Python 3.10+
- Sample documents to convert (the script includes a built-in demo using generated Markdown)

## Setup

```bash
cd examples/markitdown_to_jsonl
pip install -r requirements.txt
```

## Run

```bash
python run.py
```

## Expected Output

```
Converting sample documents...
Ingested 2 documents -> 8 chunks
Exported 8 records to output/records.jsonl

Sample record:
{
  "id": "...",
  "text": "...",
  "source_uri": "file:sample_docs/report.md",
  "section_path": ["Report", "Summary"],
  ...
}
```

## What to Try Next

- Replace the sample docs with your own PDF/DOCX files (requires `pip install markitdown`)
- Adjust chunking in `docprep.toml` to tune chunk sizes
- Pipe the JSONL output to your vector DB loader
