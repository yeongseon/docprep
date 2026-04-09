"""SQLAlchemy-backed sink for persisting and querying documents."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from docprep.exceptions import MetadataError, SinkError
from docprep.models.domain import Document
from docprep.sinks.orm import Base, ChunkRow, DocumentRow, SectionRow, domain_to_row


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

    def upsert(self, documents: Sequence[Document]) -> tuple[str, ...]:
        """Persist documents, skipping those with unchanged checksums.

        Returns source URIs that were skipped (checksum match).
        All writes happen in a single transaction.
        """
        skipped: list[str] = []

        try:
            with Session(self._engine) as session, session.begin():
                for doc in documents:
                    existing = session.execute(
                        select(DocumentRow).where(DocumentRow.source_uri == doc.source_uri)
                    ).scalar_one_or_none()

                    if existing and existing.source_checksum == doc.source_checksum:
                        skipped.append(doc.source_uri)
                        continue

                    if existing:
                        session.delete(existing)
                        session.flush()

                    row = domain_to_row(doc)
                    session.add(row)

        except (SinkError, MetadataError):
            raise
        except Exception as exc:
            raise SinkError(f"Failed to upsert documents: {exc}") from exc

        return tuple(skipped)

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
