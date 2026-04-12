# ADR-0006: Export Contract (VectorRecordV1)

**Status**: Accepted
**Date**: 2025-04-12
**Deciders**: Core team

## Context

Downstream embedding pipelines and vector stores need a stable, well-defined record schema. Without a versioned contract, any internal model change in docprep could break integrations silently. We needed to define:

1. What fields a vector record contains.
2. Which fields are mandatory vs. optional.
3. How schema evolution is managed.
4. What output format to use.

## Decision

`VectorRecordV1` is the stable output schema. Every vector record includes these mandatory fields:

| Field | Purpose |
|-------|---------|
| `id` | Chunk UUID (stable anchor-based identity) |
| `document_id` | Parent document UUID |
| `section_id` | Parent section UUID |
| `chunk_anchor` | Stable chunk anchor string |
| `section_anchor` | Parent section anchor string |
| `text` | Chunk text with optional title/heading prepended |
| `content_hash` | SHA-256 of chunk content for change detection |
| `source_uri` | Canonical URI of the source document |
| `title` | Document title |
| `section_path` | Heading hierarchy path |
| `schema_version` | Integer version of the record schema |
| `pipeline_version` | docprep package version that produced the record |
| `created_at` | ISO 8601 timestamp |
| `user_metadata` | Merged frontmatter and source metadata |

Schema evolution rules:

- `schema_version` is pinned to the current version (currently 1).
- Adding optional fields is a minor change (same schema version).
- Removing or renaming fields, or changing semantics, requires a new version (`VectorRecordV2`) and a migration path.
- The `pipeline_version` field lets consumers detect which docprep version produced a record.

JSONL (JSON Lines) is the primary output format. Each line is a self-contained JSON object representing one record. This enables streaming export without materializing all records in memory.

## Consequences

**Easier:**

- Downstream integrations have a stable contract they can rely on.
- Provenance fields (`source_uri`, `section_anchor`, `chunk_anchor`) enable debugging and traceability.
- Schema version in every record makes migration detection straightforward.
- JSONL streaming works well with Unix pipes, cloud storage, and embedding batch APIs.

**Harder:**

- Records are larger than a minimal text-only export due to mandatory provenance fields.
- Schema changes require careful version management and documentation.
- The `user_metadata` field is a flexible dict, which means consumers must handle varying shapes.
- Multiple output formats (JSONL now, potentially Parquet later) increase maintenance surface.
