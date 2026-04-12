# CLI Reference

docprep provides a command-line interface for document ingestion, export, and management.

```
docprep [--version] <command> [options]
```

## Global options

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |

## Common options

Most commands accept these shared options:

| Option | Description |
|--------|-------------|
| `--config PATH` | Path to `docprep.toml` config file |
| `--json` | Force JSON output |
| `--no-json` | Force human-readable output |

Output format defaults to the `json` setting in config, or human-readable if not set.

---

## `docprep ingest`

Ingest documents into a database.

```bash
docprep ingest [source] [options]
```

| Argument / Option | Type | Default | Description |
|-------------------|------|---------|-------------|
| `source` | positional | from config | File or directory path to ingest |
| `--db` | string | from config | SQLAlchemy database URL |
| `--log-format` | choice | `human` | Log output format: `human`, `json` |
| `--log-level` | choice | `info` | Log level: `debug`, `info`, `warning`, `error`, `critical` |
| `--error-mode` | choice | `continue_on_error` | Error handling: `fail_fast`, `continue_on_error` |
| `--resume` | flag | `false` | Resume from last checkpoint, skipping unchanged sources |
| `--checkpoint-path` | string | `.docprep-checkpoint.json` | Path to checkpoint file |
| `--workers` | int | `1` | Number of parallel workers for parse/chunk |

**Examples:**

```bash
# Ingest from config
docprep ingest

# Ingest specific directory with database
docprep ingest docs/ --db sqlite:///docs.db

# Parallel ingestion with resume support
docprep ingest docs/ --db sqlite:///docs.db --workers 4 --resume

# JSON-structured logging
docprep ingest --log-format json --log-level debug
```

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | All documents ingested successfully |
| `1` | All documents failed |
| `3` | Partial success (some documents failed) |

---

## `docprep preview`

Preview document structure and chunks without persisting to a database.

```bash
docprep preview [source] [options]
```

| Argument / Option | Type | Default | Description |
|-------------------|------|---------|-------------|
| `source` | positional | from config | File or directory path to preview |

**Examples:**

```bash
docprep preview docs/
docprep preview docs/guide.md --json
```

---

## `docprep export`

Export vector records as JSONL.

```bash
docprep export [source] [options]
```

| Argument / Option | Type | Default | Description |
|-------------------|------|---------|-------------|
| `source` | positional | from config | File or directory path |
| `-o`, `--output` | string | stdout | Output file path |
| `--format` | choice | `v1` | Record format: `v1` |
| `--changed-only` | flag | `false` | Export only added/modified records since last sync |
| `--db` | string | from config | Database URL (required for `--changed-only`) |

**Examples:**

```bash
# Export all records to file
docprep export docs/ -o records.jsonl

# Export to stdout
docprep export docs/

# Export only changes since last sync
docprep export docs/ --changed-only --db sqlite:///docs.db -o delta.jsonl
```

---

## `docprep diff`

Show document changes against persisted database state.

```bash
docprep diff [source] [options]
```

| Argument / Option | Type | Default | Description |
|-------------------|------|---------|-------------|
| `source` | positional | from config | File or directory path to diff |
| `--db` | string | from config | SQLAlchemy database URL |

**Examples:**

```bash
docprep diff docs/ --db sqlite:///docs.db
docprep diff --json
```

---

## `docprep stats`

Show database statistics (document, section, and chunk counts).

```bash
docprep stats [db] [options]
```

| Argument / Option | Type | Default | Description |
|-------------------|------|---------|-------------|
| `db` | positional | from config | SQLAlchemy database URL |

**Examples:**

```bash
docprep stats sqlite:///docs.db
docprep stats --json
```

---

## `docprep inspect`

Inspect a document, section, or chunk by source URI or UUID.

```bash
docprep inspect <query> [options]
```

| Argument / Option | Type | Default | Description |
|-------------------|------|---------|-------------|
| `query` | positional | *(required)* | Source URI, document UUID, section UUID, or chunk UUID |
| `--db` | string | from config | SQLAlchemy database URL |

**Examples:**

```bash
# By source URI
docprep inspect "file:docs/guide.md" --db sqlite:///docs.db

# By UUID
docprep inspect "a1b2c3d4-..." --db sqlite:///docs.db
```

---

## `docprep prune`

Remove stale documents that are no longer present in the source directory.

```bash
docprep prune [source] [options]
```

| Argument / Option | Type | Default | Description |
|-------------------|------|---------|-------------|
| `source` | positional | from config | File or directory path to prune against |
| `--db` | string | from config | SQLAlchemy database URL |
| `--dry-run` | flag | `false` | Preview what would be deleted |

**Examples:**

```bash
# Preview stale documents
docprep prune docs/ --db sqlite:///docs.db --dry-run

# Remove stale documents
docprep prune docs/ --db sqlite:///docs.db
```

---

## `docprep delete`

Delete a specific document by source URI.

```bash
docprep delete <uri> [options]
```

| Argument / Option | Type | Default | Description |
|-------------------|------|---------|-------------|
| `uri` | positional | *(required)* | Document source URI (e.g. `file:guide.md`) |
| `--db` | string | from config | SQLAlchemy database URL |
| `--dry-run` | flag | `false` | Preview what would be deleted |

**Examples:**

```bash
docprep delete "file:docs/old-guide.md" --db sqlite:///docs.db
docprep delete "file:docs/old-guide.md" --db sqlite:///docs.db --dry-run
```
