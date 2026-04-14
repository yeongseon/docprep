# Examples

Ready-to-run examples demonstrating docprep's document ingestion pipeline.

## Project Examples

Self-contained projects with setup instructions. Each directory includes a README, requirements, and run script.

| Example | Description | Prerequisites |
|---------|-------------|---------------|
| [markitdown_to_jsonl/](markitdown_to_jsonl/) | Convert documents via MarkItDown adapter -> JSONL export | Python 3.10+ |
| [docling_to_postgres/](docling_to_postgres/) | Docling adapter -> PostgreSQL persistence | Python 3.10+, Docker |
| [github_docs_incremental_sync/](github_docs_incremental_sync/) | Incremental sync: ingest -> edit -> re-ingest -> export delta | Python 3.10+ |
| [plugin-template/](plugin-template/) | Minimal plugin project template (copy and customize) | Python 3.10+ |

## Script Examples

Single-file scripts demonstrating specific features. Run from the repository root.

| Script | Description | Run Command |
|--------|-------------|-------------|
| [quickstart.py](quickstart.py) | Hello World - minimal 5-line ingest | `python examples/quickstart.py` |
| [markdown_to_sqlite.py](markdown_to_sqlite.py) | Ingest Markdown -> SQLite -> JSONL export | `python examples/markdown_to_sqlite.py` |
| [changed_only_export.py](changed_only_export.py) | Export only changed chunks | `python examples/changed_only_export.py` |
| [incremental_sync_demo.py](incremental_sync_demo.py) | Step-by-step incremental sync walkthrough | `python examples/incremental_sync_demo.py` |
| [adapter_markitdown.py](adapter_markitdown.py) | Custom adapter pattern (CSV->Markdown) | `python examples/adapter_markitdown.py` |
| [vector_store_integration.py](vector_store_integration.py) | Qdrant, ChromaDB, JSONL export patterns | `python examples/vector_store_integration.py` |
| [custom_plugin.py](custom_plugin.py) | Custom chunker plugin with entry-point registration | `python examples/custom_plugin.py` |
| [error_handling.py](error_handling.py) | Error modes, progress callbacks, exceptions | `python examples/error_handling.py` |
| [large_corpus.py](large_corpus.py) | Parallel ingestion, checkpoints, streaming export | `python examples/large_corpus.py` |
| [benchmark_incremental_sync.py](benchmark_incremental_sync.py) | Benchmark: re-embedding savings | `python examples/benchmark_incremental_sync.py` |
| [cli_quickstart.sh](cli_quickstart.sh) | CLI workflow walkthrough | `bash examples/cli_quickstart.sh` |

## Configuration Examples

| Config | Description |
|--------|-------------|
| [configs/minimal.toml](configs/minimal.toml) | Minimal configuration |
| [configs/standard.toml](configs/standard.toml) | Standard project configuration |
| [configs/advanced.toml](configs/advanced.toml) | Advanced multi-format configuration |
