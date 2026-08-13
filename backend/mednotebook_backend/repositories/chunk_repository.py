import uuid
from datetime import datetime, timezone

from sqlalchemy import bindparam, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk import DocumentChunk


class ChunkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_chunks_without_embeddings(
        self, document_id: uuid.UUID, batch_size: int = 50
    ) -> list[DocumentChunk]:
        """Chunks still missing an embedding, oldest chunk_index first —
        lets an interrupted embedding job resume where it left off instead
        of restarting from chunk 0.
        """
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id, DocumentChunk.embedding.is_(None))
            .order_by(DocumentChunk.chunk_index)
            .limit(batch_size)
        )
        return list(result.scalars().all())

    async def save_embedding(self, chunk_id: uuid.UUID, embedding: list[float], model_name: str) -> None:
        # Assigning a plain Python list through the ORM-mapped Vector column
        # goes through pgvector's SQLAlchemy type, which handles the
        # list -> pgvector wire format conversion — no manual casting needed.
        await self.db.execute(
            update(DocumentChunk)
            .where(DocumentChunk.id == chunk_id)
            .values(
                embedding=embedding,
                embedding_model=model_name,
                embedding_generated_at=datetime.now(timezone.utc),
            )
        )
        await self.db.commit()

    async def save_embeddings_batch(self, chunk_embeddings: list[dict]) -> int:
        """Bulk-update chunks. Each dict: {chunk_id, embedding, model_name}.

        Returns the count of chunks successfully updated.
        """
        if not chunk_embeddings:
            return 0

        now = datetime.now(timezone.utc)
        # bindparam names are prefixed with "_" so they can't collide with
        # the mapped column names referenced in .values() / .where().
        #
        # Built against DocumentChunk.__table__ (Core), not the ORM entity —
        # passing executemany-style list params to an ORM-mapped update()
        # triggers SQLAlchemy's "ORM Bulk UPDATE by Primary Key" heuristic,
        # which ignores this WHERE/bindparam setup entirely and instead
        # requires each dict to carry the actual PK column name. The plain
        # Core table sidesteps that special-casing and just runs a normal
        # executemany UPDATE.
        stmt = (
            update(DocumentChunk.__table__)
            .where(DocumentChunk.__table__.c.id == bindparam("_chunk_id"))
            .values(
                embedding=bindparam("_embedding"),
                embedding_model=bindparam("_model_name"),
                embedding_generated_at=now,
            )
        )
        params = [
            {
                "_chunk_id": item["chunk_id"],
                "_embedding": item["embedding"],
                "_model_name": item["model_name"],
            }
            for item in chunk_embeddings
        ]
        # One statement executed with a param list — SQLAlchemy dispatches
        # this as a single executemany() at the DBAPI level, not N round trips.
        result = await self.db.execute(stmt, params)
        await self.db.commit()

        # executemany-style updates don't reliably report a per-batch
        # rowcount on every driver/dialect combination — fall back to
        # "all rows attempted" when the driver doesn't give us a real number.
        updated = result.rowcount
        return updated if updated is not None and updated >= 0 else len(chunk_embeddings)

    async def get_embedding_progress(self, document_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(
                func.count(DocumentChunk.id),
                func.count(DocumentChunk.embedding),  # COUNT ignores NULLs
            ).where(DocumentChunk.document_id == document_id)
        )
        total_chunks, embedded_chunks = result.one()
        pending_chunks = total_chunks - embedded_chunks
        progress_percent = round(embedded_chunks / total_chunks * 100) if total_chunks else 0
        return {
            "total_chunks": total_chunks,
            "embedded_chunks": embedded_chunks,
            "pending_chunks": pending_chunks,
            "progress_percent": progress_percent,
        }