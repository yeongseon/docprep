# Configuration Reference

docprep uses a TOML configuration file (`docprep.toml`) for project settings. This document covers every available option.

## Config discovery

docprep searches for `docprep.toml` starting in the current directory and walking up to parent directories. The first file found is used.

**Precedence** (highest to lowest):

1. CLI arguments (e.g. `--db`, `source` positional)
2. Environment variable overrides (`DOCPREP_...`)
3. Config file (`--config PATH` or auto-discovered `docprep.toml`)
4. Built-in defaults

## Environment variable overrides

docprep reads environment variables with the `DOCPREP_` prefix and applies them as config overrides.

- Use a single `_` for root fields (for example, `DOCPREP_SOURCE`).
- Use `__` (double underscore) for nested fields (for example, `DOCPREP_SINK__DATABASE_URL`).
- Boolean values accept `true`/`false`/`1`/`0` (case-insensitive).

Supported variables:

- `DOCPREP_SOURCE` -> `source`
- `DOCPREP_JSON` -> `json`
- `DOCPREP_SINK__DATABASE_URL` -> `sink.database_url`
- `DOCPREP_SINK__CREATE_TABLES` -> `sink.create_tables`
- `DOCPREP_EXPORT__TEXT_PREPEND` -> `export.text_prepend`
- `DOCPREP_EXPORT__INCLUDE_ANNOTATIONS` -> `export.include_annotations`

## Root options

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `source` | string | *(none)* | Path to source file or directory |
| `json` | bool | `false` | Default output format for CLI commands |

## `[loader]` section

Controls how source files are discovered and read.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `type` | string | `"filesystem"` | Loader type: `"markdown"` or `"filesystem"` |

### Markdown loader (`type = "markdown"`)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `glob_pattern` | string | `"**/*.md"` | Glob pattern for file discovery |

### Filesystem loader (`type = "filesystem"`)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `include_globs` | list[string] | `["**/*.md", "**/*.txt", "**/*.html", "**/*.htm"]` | Glob patterns to include |
| `exclude_globs` | list[string] | `[]` | Glob patterns to exclude |
| `hidden_policy` | string | `"skip"` | Hidden file handling: `"skip"` or `"include"` |
| `symlink_policy` | string | `"follow"` | Symlink handling: `"follow"` or `"skip"` |
| `encoding` | string | `"utf-8"` | File encoding |
| `encoding_errors` | string | `"strict"` | Encoding error handling (Python codec error mode) |

## `[parser]` section

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `type` | string | `"auto"` | Parser type: `"markdown"`, `"plaintext"`, `"html"`, `"rst"`, or `"auto"` |

The `"auto"` parser dispatches to the appropriate parser based on file extension.

## `[[chunkers]]` section

Chunkers are applied in order. Define multiple `[[chunkers]]` entries to build a pipeline.

### Heading chunker (`type = "heading"`)

Splits documents into sections by heading boundaries.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `type` | string | — | Must be `"heading"` |

### Size chunker (`type = "size"`)

Splits sections into chunks by character count.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `type` | string | — | Must be `"size"` |
| `max_chars` | int | `1500` | Maximum characters per chunk |
| `overlap_chars` | int | `0` | Character overlap between chunks |
| `min_chars` | int | `0` | Minimum characters for a chunk |

### Token chunker (`type = "token"`)

Splits sections into chunks by token budget.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `type` | string | — | Must be `"token"` |
| `max_tokens` | int | `512` | Maximum tokens per chunk |
| `overlap_tokens` | int | `0` | Token overlap between chunks |
| `tokenizer` | string | `"whitespace"` | Tokenizer: `"whitespace"` or `"character"` |

## `[sink]` section

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `type` | string | `"sqlalchemy"` | Sink type (currently only `"sqlalchemy"`) |
| `database_url` | string | *(none)* | SQLAlchemy database URL (e.g. `"sqlite:///docs.db"`) |
| `create_tables` | bool | `true` | Auto-create database tables on first use |

## `[export]` section

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `text_prepend` | string | `"title_and_heading_path"` | Text prepend strategy (see below) |
| `include_annotations` | bool | `false` | Include structural annotations in export |

**Text prepend strategies:**

| Value | Description |
|-------|-------------|
| `"none"` | Raw chunk content only |
| `"title_only"` | Prepend document title |
| `"heading_path"` | Prepend heading hierarchy (e.g. `Guide > Installation`) |
| `"title_and_heading_path"` | Prepend both title and heading path |

## Example configurations

### Minimal

```toml
source = "docs/"
```

### Standard

```toml
source = "docs/"

[sink]
database_url = "sqlite:///docs.db"
create_tables = true

[[chunkers]]
type = "heading"

[[chunkers]]
type = "token"
max_tokens = 512
```

### Advanced

```toml
source = "content/"

[loader]
type = "filesystem"
include_globs = ["**/*.md", "**/*.rst", "**/*.html"]
exclude_globs = ["**/drafts/**", "**/node_modules/**"]
hidden_policy = "skip"
symlink_policy = "follow"
encoding = "utf-8"

[parser]
type = "auto"

[[chunkers]]
type = "heading"

[[chunkers]]
type = "token"
max_tokens = 512
overlap_tokens = 50
tokenizer = "whitespace"

[sink]
type = "sqlalchemy"
database_url = "postgresql://user:pass@localhost/docprep"
create_tables = true

[export]
text_prepend = "title_and_heading_path"
include_annotations = true
```

See [`examples/configs/`](https://github.com/yeongseon/docprep/tree/main/examples/configs) for ready-to-use configuration files.
