"""SQLAlchemy-backed sink for persisting and querying documents."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import time
from typing import cast
import uuid

from sqlalchemy import Engine, delete, func, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from ..exceptions import MetadataError, SinkError
from ..ids import SCHEMA_VERSION
from ..models.domain import (
    Chunk,
    DeletePolicy,
    DeleteResult,
    Document,
    DocumentRevision,
    Page,
    RunManifest,
    Section,
    SinkUpsertResult,
    SourceScope,
    SyncResult,
)
from ..scope import compute_stale_uris, uri_in_scope
from .orm import (
    Base,
    ChunkRow,
    DocprepMeta,
    DocumentRevisionRow,
    DocumentRow,
    IngestionRunRow,
    SectionRow,
    domain_to_row,
    revision_from_document,
    row_to_chunk,
    row_to_document_summary,
    row_to_domain,
    row_to_revision,
    row_to_run_manifest,
    row_to_section,
    run_manifest_to_row,
)

_MAX_UPSERT_RETRIES = 3


@dataclass(kw_only=True, slots=True)
class Stats:
    documents: int
    sections: int
    chunks: int


class SQLAlchemySink:
    """Persists documents to a SQL database via SQLAlchemy."""

    def __init__(self, *, engine: Engine, create_tables: bool = True) -> None:
        self._engine = engine
        if create_tables:
            Base.metadata.create_all(engine)
            self._ensure_schema_version()

    def _ensure_schema_version(self) -> None:
        with Session(self._engine) as session, session.begin():
            stored = session.execute(
                select(DocprepMeta.value).where(DocprepMeta.key == "schema_version")
            ).scalar_one_or_none()

            if stored is None:
                session.add(DocprepMeta(key="schema_version", value=str(SCHEMA_VERSION)))
                return

            if stored != str(SCHEMA_VERSION):
                raise SinkError(
                    "Database schema version "
                    f"{stored} does not match docprep schema version {SCHEMA_VERSION}. "
                    "Run 'docprep migrate --db <url>' or recreate the database."
                )

    def migrate(self) -> None:
        """Run idempotent migrations to bring database to current schema version."""
        with Session(self._engine) as session, session.begin():
            Base.metadata.create_all(self._engine)

            stored = session.execute(
                select(DocprepMeta.value).where(DocprepMeta.key == "schema_version")
            ).scalar_one_or_none()

            current_version = int(stored) if stored is not None else 0
            if current_version >= SCHEMA_VERSION:
                return

            if current_version < 1:
                self._migrate_v0_to_v1(session)

            if stored is None:
                session.add(DocprepMeta(key="schema_version", value=str(SCHEMA_VERSION)))
            else:
                session.execute(
                    update(DocprepMeta)
                    .where(DocprepMeta.key == "schema_version")
                    .values(value=str(SCHEMA_VERSION))
                )

    def _migrate_v0_to_v1(self, session: Session) -> None:
        migrations = [
            "ALTER TABLE documents ADD COLUMN identity_version INTEGER NOT NULL DEFAULT 2",
            "ALTER TABLE sections ADD COLUMN anchor VARCHAR(512) NOT NULL DEFAULT ''",
            "ALTER TABLE sections ADD COLUMN content_hash VARCHAR(16) NOT NULL DEFAULT ''",
            "ALTER TABLE chunks ADD COLUMN anchor VARCHAR(1024) NOT NULL DEFAULT ''",
            "ALTER TABLE chunks ADD COLUMN content_hash VARCHAR(16) NOT NULL DEFAULT ''",
            "ALTER TABLE chunks ADD COLUMN char_start INTEGER",
            "ALTER TABLE chunks ADD COLUMN char_end INTEGER",
            "ALTER TABLE chunks ADD COLUMN token_count INTEGER",
            (
                "CREATE TABLE ingestion_runs ("
                "id VARCHAR(36) PRIMARY KEY, "
                "scope_prefixes JSON, "
                "scope_explicit BOOLEAN NOT NULL DEFAULT 0, "
                "source_uris_seen JSON, "
                "timestamp VARCHAR(32) NOT NULL"
                ")"
            ),
            (
                "CREATE TABLE document_revisions ("
                "id VARCHAR(36) PRIMARY KEY, "
                "document_id VARCHAR(36) NOT NULL, "
                "source_uri VARCHAR(1024) NOT NULL, "
                "source_checksum VARCHAR(64) NOT NULL, "
                "revision_number INTEGER NOT NULL, "
                "ingestion_run_id VARCHAR(36), "
                "section_anchors JSON, "
                "chunk_anchors JSON, "
                "section_hashes JSON, "
                "chunk_hashes JSON, "
                "is_current BOOLEAN NOT NULL DEFAULT 1, "
                "timestamp VARCHAR(32) NOT NULL"
                ")"
            ),
            "CREATE INDEX ix_revisions_document_id ON document_revisions (document_id)",
            "CREATE INDEX ix_revisions_timestamp ON document_revisions (timestamp)",
        ]

        for migration in migrations:
            try:
                session.execute(text(migration))
            except (OperationalError, ProgrammingError) as exc:
                if not (
                    _is_duplicate_column_error(exc)
                    or _is_duplicate_table_error(exc)
                    or _is_duplicate_index_error(exc)
                ):
                    raise

    def record_run(self, manifest: RunManifest) -> None:
        try:
            with Session(self._engine) as session, session.begin():
                session.merge(run_manifest_to_row(manifest))
        except Exception as exc:
            raise SinkError(f"Failed to record ingestion run: {exc}") from exc

    def get_stored_uris_in_scope(self, scope: SourceScope) -> set[str]:
        with Session(self._engine) as session:
            stored_uris = set(session.execute(select(DocumentRow.source_uri)).scalars().all())
        return {uri for uri in stored_uris if uri_in_scope(uri, scope)}

    def get_latest_run(self) -> RunManifest | None:
        with Session(self._engine) as session:
            latest = session.execute(
                select(IngestionRunRow).order_by(IngestionRunRow.timestamp.desc()).limit(1)
            ).scalar_one_or_none()
        if latest is None:
            return None
        return row_to_run_manifest(latest)

    def get_document(self, source_uri: str) -> Document | None:
        """Get a single document by source_uri, with all sections and chunks."""
        with Session(self._engine) as session:
            row = session.execute(
                select(DocumentRow).where(DocumentRow.source_uri == source_uri)
            ).scalar_one_or_none()
            if row is None:
                return None
            return cast(Document, row_to_domain(row))

    def list_documents(self, *, offset: int = 0, limit: int = 50) -> Page:
        """List documents with pagination."""
        with Session(self._engine) as session:
            total = session.execute(select(func.count(DocumentRow.id))).scalar_one()
            rows = (
                session.execute(
                    select(DocumentRow).order_by(DocumentRow.source_uri).offset(offset).limit(limit)
                )
                .scalars()
                .all()
            )

        return Page(
            items=tuple(cast(Document, row_to_document_summary(row)) for row in rows),
            total=total,
            offset=offset,
            limit=limit,
            has_more=offset + limit < total,
        )

    def get_section(self, section_id: uuid.UUID) -> Section | None:
        """Get a single section by ID."""
        with Session(self._engine) as session:
            row = session.execute(
                select(SectionRow).where(SectionRow.id == str(section_id))
            ).scalar_one_or_none()
        if row is None:
            return None
        return cast(Section, row_to_section(row))

    def list_sections(self, document_id: uuid.UUID, *, offset: int = 0, limit: int = 50) -> Page:
        """List sections for a document with pagination."""
        with Session(self._engine) as session:
            total = session.execute(
                select(func.count(SectionRow.id)).where(SectionRow.document_id == str(document_id))
            ).scalar_one()
            rows = (
                session.execute(
                    select(SectionRow)
                    .where(SectionRow.document_id == str(document_id))
                    .order_by(SectionRow.order_index)
                    .offset(offset)
                    .limit(limit)
                )
                .scalars()
                .all()
            )

        return Page(
            items=tuple(cast(Section, row_to_section(row)) for row in rows),
            total=total,
            offset=offset,
            limit=limit,
            has_more=offset + limit < total,
        )

    def get_chunk(self, chunk_id: uuid.UUID) -> Chunk | None:
        """Get a single chunk by ID."""
        with Session(self._engine) as session:
            row = session.execute(
                select(ChunkRow).where(ChunkRow.id == str(chunk_id))
            ).scalar_one_or_none()
        if row is None:
            return None
        return cast(Chunk, row_to_chunk(row))

    def list_chunks(self, document_id: uuid.UUID, *, offset: int = 0, limit: int = 50) -> Page:
        """List chunks for a document with pagination."""
        with Session(self._engine) as session:
            total = session.execute(
                select(func.count(ChunkRow.id)).where(ChunkRow.document_id == str(document_id))
            ).scalar_one()
            rows = (
                session.execute(
                    select(ChunkRow)
                    .where(ChunkRow.document_id == str(document_id))
                    .order_by(ChunkRow.order_index)
                    .offset(offset)
                    .limit(limit)
                )
                .scalars()
                .all()
            )

        return Page(
            items=tuple(cast(Chunk, row_to_chunk(row)) for row in rows),
            total=total,
            offset=offset,
            limit=limit,
            has_more=offset + limit < total,
        )

    def get_chunks_by_section(
        self, section_id: uuid.UUID, *, offset: int = 0, limit: int = 50
    ) -> Page:
        """List chunks for a section with pagination."""
        with Session(self._engine) as session:
            total = session.execute(
                select(func.count(ChunkRow.id)).where(ChunkRow.section_id == str(section_id))
            ).scalar_one()
            rows = (
                session.execute(
                    select(ChunkRow)
                    .where(ChunkRow.section_id == str(section_id))
                    .order_by(ChunkRow.section_chunk_index)
                    .offset(offset)
                    .limit(limit)
                )
                .scalars()
                .all()
            )

        return Page(
            items=tuple(cast(Chunk, row_to_chunk(row)) for row in rows),
            total=total,
            offset=offset,
            limit=limit,
            has_more=offset + limit < total,
        )

    def get_document_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Get a single document by its UUID, with all sections and chunks."""
        with Session(self._engine) as session:
            row = session.execute(
                select(DocumentRow).where(DocumentRow.id == str(document_id))
            ).scalar_one_or_none()
            if row is None:
                return None
            return cast(Document, row_to_domain(row))

    def upsert(
        self,
        documents: Sequence[Document],
        *,
        run_id: uuid.UUID | None = None,
    ) -> SinkUpsertResult:
        """Persist documents, classifying results as skipped or updated.

        Skipped = checksum unchanged, Updated = new or changed checksum.
        All writes happen in a single transaction.
        """
        skipped: list[str] = []
        updated: list[str] = []

        for attempt in range(1, _MAX_UPSERT_RETRIES + 1):
            skipped.clear()
            updated.clear()
            try:
                with Session(self._engine) as session:
                    try:
                        with session.begin():
                            for doc in documents:
                                existing = session.execute(
                                    select(DocumentRow).where(
                                        DocumentRow.source_uri == doc.source_uri
                                    )
                                ).scalar_one_or_none()

                                if (
                                    existing
                                    and existing.source_checksum == doc.source_checksum
                                    and existing.identity_version == doc.identity_version
                                ):
                                    skipped.append(doc.source_uri)
                                    continue

                                if existing:
                                    session.execute(
                                        delete(ChunkRow).where(ChunkRow.document_id == existing.id)
                                    )
                                    session.execute(
                                        delete(SectionRow).where(
                                            SectionRow.document_id == existing.id
                                        )
                                    )
                                    session.delete(existing)
                                    session.flush()

                                session.execute(
                                    update(DocumentRevisionRow)
                                    .where(DocumentRevisionRow.document_id == str(doc.id))
                                    .where(DocumentRevisionRow.is_current.is_(True))
                                    .values(is_current=False)
                                )
                                latest_revision_number = session.execute(
                                    select(func.max(DocumentRevisionRow.revision_number)).where(
                                        DocumentRevisionRow.document_id == str(doc.id)
                                    )
                                ).scalar_one()
                                next_revision_number = (latest_revision_number or 0) + 1
                                revision = revision_from_document(
                                    doc,
                                    revision_number=next_revision_number,
                                    run_id=run_id,
                                    timestamp=datetime.now(timezone.utc).isoformat(),
                                )
                                row = domain_to_row(doc)
                                session.add(row)
                                session.add(revision)
                                updated.append(doc.source_uri)
                    except IntegrityError:
                        session.rollback()
                        raise
                break
            except IntegrityError:
                if attempt == _MAX_UPSERT_RETRIES:
                    raise SinkError(
                        f"Failed to upsert documents after {_MAX_UPSERT_RETRIES} retries "
                        "due to concurrent modifications"
                    )
                time.sleep(0.05 * attempt)
                continue
            except (SinkError, MetadataError):
                raise
            except Exception as exc:
                raise SinkError(f"Failed to upsert documents: {exc}") from exc

        return SinkUpsertResult(
            skipped_source_uris=tuple(skipped),
            updated_source_uris=tuple(updated),
        )

    def delete_by_uri(self, source_uri: str, *, dry_run: bool = False) -> DeleteResult:
        """Delete a single document and all its sections/chunks by source_uri."""
        with Session(self._engine) as session, session.begin():
            doc_row = session.execute(
                select(DocumentRow).where(DocumentRow.source_uri == source_uri)
            ).scalar_one_or_none()
            if doc_row is None:
                return DeleteResult(dry_run=dry_run)

            section_count = session.execute(
                select(func.count(SectionRow.id)).where(SectionRow.document_id == doc_row.id)
            ).scalar_one()
            chunk_count = session.execute(
                select(func.count(ChunkRow.id)).where(ChunkRow.document_id == doc_row.id)
            ).scalar_one()
            document_ids = [doc_row.id]
            revision_count = session.execute(
                select(func.count(DocumentRevisionRow.id)).where(
                    DocumentRevisionRow.document_id.in_(document_ids)
                )
            ).scalar_one()

            if not dry_run:
                session.execute(delete(ChunkRow).where(ChunkRow.document_id == doc_row.id))
                session.execute(delete(SectionRow).where(SectionRow.document_id == doc_row.id))
                session.execute(
                    delete(DocumentRevisionRow).where(
                        DocumentRevisionRow.document_id.in_(document_ids)
                    )
                )
                session.delete(doc_row)

            return DeleteResult(
                deleted_source_uris=(source_uri,),
                deleted_document_count=1,
                deleted_section_count=section_count,
                deleted_chunk_count=chunk_count,
                deleted_revision_count=revision_count,
                dry_run=dry_run,
            )

    def delete_by_prefix(self, prefix: str, *, dry_run: bool = False) -> DeleteResult:
        """Delete all documents whose source_uri starts with the given prefix."""
        with Session(self._engine) as session, session.begin():
            rows = (
                session.execute(
                    select(DocumentRow)
                    .where(DocumentRow.source_uri.startswith(prefix))
                    .order_by(DocumentRow.source_uri)
                )
                .scalars()
                .all()
            )
            if not rows:
                return DeleteResult(dry_run=dry_run)

            source_uris = tuple(row.source_uri for row in rows)
            document_ids = [row.id for row in rows]

            section_count = session.execute(
                select(func.count(SectionRow.id)).where(SectionRow.document_id.in_(document_ids))
            ).scalar_one()
            chunk_count = session.execute(
                select(func.count(ChunkRow.id)).where(ChunkRow.document_id.in_(document_ids))
            ).scalar_one()
            revision_count = session.execute(
                select(func.count(DocumentRevisionRow.id)).where(
                    DocumentRevisionRow.document_id.in_(document_ids)
                )
            ).scalar_one()

            if not dry_run:
                session.execute(delete(ChunkRow).where(ChunkRow.document_id.in_(document_ids)))
                session.execute(delete(SectionRow).where(SectionRow.document_id.in_(document_ids)))
                session.execute(
                    delete(DocumentRevisionRow).where(
                        DocumentRevisionRow.document_id.in_(document_ids)
                    )
                )
                session.execute(delete(DocumentRow).where(DocumentRow.id.in_(document_ids)))

            return DeleteResult(
                deleted_source_uris=source_uris,
                deleted_document_count=len(source_uris),
                deleted_section_count=section_count,
                deleted_chunk_count=chunk_count,
                deleted_revision_count=revision_count,
                dry_run=dry_run,
            )

    def delete_by_uris(self, source_uris: Sequence[str], *, dry_run: bool = False) -> DeleteResult:
        """Delete multiple documents by explicit source_uri list."""
        ordered_uris = tuple(dict.fromkeys(source_uris))
        if not ordered_uris:
            return DeleteResult(dry_run=dry_run)

        with Session(self._engine) as session, session.begin():
            rows = session.execute(
                select(DocumentRow.id, DocumentRow.source_uri).where(
                    DocumentRow.source_uri.in_(ordered_uris)
                )
            ).all()
            if not rows:
                return DeleteResult(dry_run=dry_run)

            id_by_uri = {row.source_uri: row.id for row in rows}
            found_source_uris = tuple(uri for uri in ordered_uris if uri in id_by_uri)
            document_ids = [id_by_uri[uri] for uri in found_source_uris]

            section_count = session.execute(
                select(func.count(SectionRow.id)).where(SectionRow.document_id.in_(document_ids))
            ).scalar_one()
            chunk_count = session.execute(
                select(func.count(ChunkRow.id)).where(ChunkRow.document_id.in_(document_ids))
            ).scalar_one()
            revision_count = session.execute(
                select(func.count(DocumentRevisionRow.id)).where(
                    DocumentRevisionRow.document_id.in_(document_ids)
                )
            ).scalar_one()

            if not dry_run:
                session.execute(delete(ChunkRow).where(ChunkRow.document_id.in_(document_ids)))
                session.execute(delete(SectionRow).where(SectionRow.document_id.in_(document_ids)))
                session.execute(
                    delete(DocumentRevisionRow).where(
                        DocumentRevisionRow.document_id.in_(document_ids)
                    )
                )
                session.execute(delete(DocumentRow).where(DocumentRow.id.in_(document_ids)))

            return DeleteResult(
                deleted_source_uris=found_source_uris,
                deleted_document_count=len(found_source_uris),
                deleted_section_count=section_count,
                deleted_chunk_count=chunk_count,
                deleted_revision_count=revision_count,
                dry_run=dry_run,
            )

    def sync(
        self,
        documents: Sequence[Document],
        *,
        scope: SourceScope,
        run_id: uuid.UUID | None = None,
        delete_policy: DeletePolicy = DeletePolicy.HARD_DELETE,
        dry_run: bool = False,
    ) -> SyncResult:
        """Upsert documents, then prune stale documents within scope."""
        if dry_run:
            existing_checksum_by_uri: dict[str, str] = {}
            ordered_uris = tuple(dict.fromkeys(doc.source_uri for doc in documents))
            if ordered_uris:
                with Session(self._engine) as session:
                    existing_rows = session.execute(
                        select(DocumentRow.source_uri, DocumentRow.source_checksum).where(
                            DocumentRow.source_uri.in_(ordered_uris)
                        )
                    ).all()
                existing_checksum_by_uri = {
                    row.source_uri: row.source_checksum for row in existing_rows
                }

            skipped = []
            updated = []
            for document in documents:
                existing_checksum = existing_checksum_by_uri.get(document.source_uri)
                if existing_checksum == document.source_checksum:
                    skipped.append(document.source_uri)
                else:
                    updated.append(document.source_uri)

            upsert_result = SinkUpsertResult(
                skipped_source_uris=tuple(skipped),
                updated_source_uris=tuple(updated),
            )
        else:
            upsert_result = self.upsert(documents, run_id=run_id)

        seen_uris = {doc.source_uri for doc in documents}
        stored_uris_in_scope = self.get_stored_uris_in_scope(scope)
        stale_uris = compute_stale_uris(
            scope, seen_uris=seen_uris, stored_uris=stored_uris_in_scope
        )

        if delete_policy == DeletePolicy.HARD_DELETE and stale_uris:
            delete_result = self.delete_by_uris(tuple(sorted(stale_uris)), dry_run=dry_run)
        else:
            delete_result = DeleteResult(dry_run=dry_run)

        return SyncResult(
            upsert_result=SinkUpsertResult(
                skipped_source_uris=upsert_result.skipped_source_uris,
                updated_source_uris=upsert_result.updated_source_uris,
                deleted_source_uris=delete_result.deleted_source_uris,
            ),
            delete_result=delete_result,
        )

    def get_current_revision(self, document_id: uuid.UUID) -> DocumentRevision | None:
        with Session(self._engine) as session:
            revision_row = session.execute(
                select(DocumentRevisionRow)
                .where(DocumentRevisionRow.document_id == str(document_id))
                .where(DocumentRevisionRow.is_current.is_(True))
                .order_by(DocumentRevisionRow.revision_number.desc())
                .limit(1)
            ).scalar_one_or_none()
        if revision_row is None:
            return None
        return cast(DocumentRevision, row_to_revision(revision_row))

    def get_previous_revision(self, document_id: uuid.UUID) -> DocumentRevision | None:
        with Session(self._engine) as session:
            revision_row = session.execute(
                select(DocumentRevisionRow)
                .where(DocumentRevisionRow.document_id == str(document_id))
                .where(DocumentRevisionRow.is_current.is_(False))
                .order_by(DocumentRevisionRow.revision_number.desc())
                .limit(1)
            ).scalar_one_or_none()
        if revision_row is None:
            return None
        return cast(DocumentRevision, row_to_revision(revision_row))

    def get_revisions(
        self,
        document_id: uuid.UUID,
        limit: int | None = None,
    ) -> list[DocumentRevision]:
        query = (
            select(DocumentRevisionRow)
            .where(DocumentRevisionRow.document_id == str(document_id))
            .order_by(DocumentRevisionRow.revision_number.desc())
        )
        if limit is not None:
            query = query.limit(limit)

        with Session(self._engine) as session:
            revision_rows = session.execute(query).scalars().all()

        return [cast(DocumentRevision, row_to_revision(row)) for row in revision_rows]

    def prune_revisions(self, max_depth: int = 10) -> int:
        if max_depth < 0:
            raise ValueError("max_depth must be >= 0")

        with Session(self._engine) as session, session.begin():
            revision_rows = (
                session.execute(
                    select(DocumentRevisionRow).order_by(
                        DocumentRevisionRow.document_id,
                        DocumentRevisionRow.revision_number.desc(),
                    )
                )
                .scalars()
                .all()
            )

            retained_counts: dict[str, int] = {}
            deleted_count = 0
            for row in revision_rows:
                retained_count = retained_counts.get(row.document_id, 0)
                if retained_count >= max_depth:
                    session.delete(row)
                    deleted_count += 1
                    continue

                retained_counts[row.document_id] = retained_count + 1

            return deleted_count

    def stats(self) -> Stats:
        with Session(self._engine) as session:
            doc_count = session.execute(select(func.count(DocumentRow.id))).scalar_one()
            sec_count = session.execute(select(func.count(SectionRow.id))).scalar_one()
            chunk_count = session.execute(select(func.count(ChunkRow.id))).scalar_one()

        return Stats(
            documents=doc_count,
            sections=sec_count,
            chunks=chunk_count,
        )


def _is_duplicate_column_error(exc: OperationalError | ProgrammingError) -> bool:
    message = str(exc).lower()
    return "duplicate column name" in message or "already exists" in message


def _is_duplicate_table_error(exc: OperationalError | ProgrammingError) -> bool:
    message = str(exc).lower()
    return (
        "table ingestion_runs already exists" in message
        or "table document_revisions already exists" in message
    )


def _is_duplicate_index_error(exc: OperationalError | ProgrammingError) -> bool:
    message = str(exc).lower()
    return "index ix_revisions_document_id already exists" in message or (
        "index ix_revisions_timestamp already exists" in message
    )
