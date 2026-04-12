# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

## [0.1.0] - 2026-04-12

### Added

- **Identity model v2**: Anchor-based stable section IDs (hierarchical heading path) and content-hash chunk IDs. Deterministic identity across re-ingestion.
- **URI canonicalization**: Source URIs normalized with `file:` scheme prefix, resolved relative to source root. Same file always produces same `document_id`.
- **Schema versioning**: `SCHEMA_VERSION` constant, `docprep_meta` table tracks DB schema version, `SQLAlchemySink.migrate()` for idempotent upgrades.
- **VectorRecordV1 export contract**: Typed export with provenance metadata (`pipeline_version`, `created_at`), content metrics (`char_count`, `content_hash`).
- **TextPrependStrategy**: Configurable text context prepend — `none`, `title_only`, `heading_path`, `title_and_heading_path`.
- **Markdown-safe chunk boundaries**: Chunks never split inside code blocks, lists, or block quotes. Boundary metadata in `Chunk.metadata`.
- **Token-aware chunker**: `TokenChunker` with pluggable tokenizer (`whitespace` or `character`), configurable `max_tokens` and `overlap_tokens`.
- **Diff engine**: `compute_diff()` and `compute_diff_from_documents()` for structural change detection between document revisions.
- **Document revision history**: `DocumentRevision` model, revision tracking in SQLAlchemy sink, `get_revision_history()` API.
- **Scope and prune semantics**: `SourceScope`, `uri_in_scope()`, batch scope derivation, `prune()` for removing out-of-scope documents.
- **Sync and delete operations**: `sync()` for full reconciliation, `delete_by_source_uri()` / `delete_by_document_id()` with revision cleanup.
- **Typed read/query API**: `get_document()`, `list_documents()`, `get_stored_uris_in_scope()` on SQLAlchemy sink.
- **CLI operator workflows**: `docprep diff`, `docprep stats`, `docprep inspect`, `docprep prune`, `docprep delete`, `docprep export` commands.
- **FileSystemLoader**: Multi-format file loading with glob patterns, encoding control, hidden/symlink policies.
- **Multi-format parsers**: `PlainTextParser`, `HtmlParser` (stdlib only), `RstParser` (heading adornments, field lists), `MultiFormatParser` (auto-dispatch by media type).
- **Plugin registry**: Entry-point based plugin discovery via `importlib.metadata`. Third-party loaders, parsers, chunkers, sinks, and adapters.
- **Adapter protocol**: `Adapter` protocol in `docprep.adapters.protocol` for external document converters.
- **Streaming JSONL export**: `iter_vector_records()`, `iter_vector_records_v1()`, `write_jsonl()`, `ExportDelta`, `build_export_delta()`.
- **CLI export command**: `docprep export` with `--changed-only` and `-o` flags for incremental JSONL export.
- **Evaluation framework**: `EvalCorpus`, `EvalQuery`, `AnswerSpan` for chunking quality evaluation. `ChunkingMetrics`, `RetrievalMetrics`, `run_benchmark()` harness.
- **Architecture Decision Records**: 6 ADRs documenting identity model, adapter pattern, chunking strategy, plugin registry, diff-then-sync, and export contract.
- **Production documentation**: README with positioning, comparison table, format matrix, config reference, CLI reference, architecture overview, plugin system docs.
- **Example configs**: `examples/configs/` — minimal, standard, and advanced `docprep.toml` configurations.
- **Example scripts**: `examples/markdown_to_sqlite.py`, `examples/changed_only_export.py`.

### Changed

- **BREAKING**: Identity model v2 — section IDs now based on hierarchical anchors instead of order index; chunk IDs based on content hash instead of chunk index. All stored IDs will change on re-ingestion.
- **BREAKING**: Ingest stage label renamed from `sink` to `persist`. `PipelineStage` enum replaces `Literal[...]` annotations.
- `Ingestor` default (no config) now uses `[HeadingChunker(), SizeChunker()]`, matching CLI behavior. Canonical default defined in `DEFAULT_CHUNKERS`.
- `DeletePolicy` enum: removed unimplemented `SOFT_DELETE` variant.
- `Sink.upsert()` signature now accepts optional `run_id: uuid.UUID | None = None`.

### Bug Fixes

- Align default chunking pipeline between CLI and Python API (#41).
- Fix `uri_in_scope()` handling of bare `"file:"` root prefix (#C3).
- Fix `delete_by_*` operations to clean up `DocumentRevisionRow` entries (#C1).
- Remove duplicate `_uri_matches_scope` from CLI; use canonical `uri_in_scope` from `scope.py` (#C4).

### Tests

- 490 tests, 2 skipped, ≥90% coverage.
- Golden markdown fixtures with snapshot-pinned section/chunk assertions.
- Hypothesis-based ingestion invariant tests for UUID determinism, chunk coverage, ordering, and size bounds.
- Comprehensive test suites for all new modules: filesystem loader, parsers (plaintext, HTML, RST, multi), token chunker, diff engine, revision history, scope, sync/delete, CLI ops, export JSONL, plugins, eval framework.

## [0.0.1] - 2026-04-11

### Features

- Implement complete docprep v0.0.1

### Miscellaneous Tasks

- Initial project scaffold
<!-- generated by git-cliff -->
