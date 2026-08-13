import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mednotebook_backend.config import settings
from mednotebook_backend.database import async_url
from mednotebook_backend.models.audit import AuditLog
from mednotebook_backend.models.chunk import ChunkType, DocumentChunk
from mednotebook_backend.models.document import Document, DocumentStatus
from mednotebook_backend.models.embedding_cost import EmbeddingCost
from mednotebook_backend.repositories.chunk_repository import ChunkRepository
from mednotebook_backend.services import storage as storage_service
from mednotebook_backend.services.chunker import ChunkingConfig, chunk_text
from mednotebook_backend.services.embeddings import estimate_embedding_cost, generate_embeddings_batch
from mednotebook_backend.services.parsers import get_parser
from worker import celery_app

logger = logging.getLogger("mednotebook.tasks.document")

_CHUNK_INSERT_BATCH_SIZE = 100
_EMBED_BATCH_SIZE = 50


class _DocumentNotFound(Exception):
    """No matching document row — nothing to process, nothing to retry."""


class _PermanentTaskError(Exception):
    """A failure that retrying can't fix (e.g. a corrupt file) — the task
    should fail immediately rather than retry.
    """


def _make_session_factory():
    # A fresh engine per call, not the FastAPI process's shared singleton —
    # asyncpg connections are bound to the event loop that opened them, and
    # every Celery task gets its own asyncio.run() loop.
    engine = create_async_engine(async_url(settings.database_url), echo=False)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _mark_error(document_id: uuid.UUID, error_message: str) -> None:
    engine, session_factory = _make_session_factory()
    try:
        async with session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                return
            doc.status = DocumentStatus.error
            doc.error_message = error_message
            doc.embedding_status = "error"
            await db.commit()
    finally:
        await engine.dispose()


async def _mark_embedding_error(document_id: uuid.UUID, error_message: str) -> None:
    engine, session_factory = _make_session_factory()
    try:
        async with session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                return
            # Parsing already succeeded — leave `status` at "ready" rather
            # than "error". The document is still fully viewable; it's just
            # not searchable until embedding is retried.
            doc.embedding_status = "error"
            await db.commit()
        logger.error("Embedding permanently failed for document %s: %s", document_id, error_message)
    finally:
        await engine.dispose()


async def _run_parse(document_id: uuid.UUID) -> None:
    engine, session_factory = _make_session_factory()
    try:
        # ── Step 1: load document, mark processing ──────────────────────────
        async with session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                logger.error("document %s not found — nothing to process", document_id)
                raise _DocumentNotFound(str(document_id))

            doc.status = DocumentStatus.processing
            doc.processing_started_at = datetime.now(timezone.utc)
            await db.commit()
            file_key, mime_type, filename = doc.file_key, doc.mime_type, doc.filename

        logger.info("Processing started for %s (%s)", filename, mime_type)

        # ── Step 2: download from S3 ─────────────────────────────────────────
        try:
            file_content = storage_service.download_file(file_key)
        except Exception as exc:
            raise RuntimeError("Failed to download file from storage") from exc

        # ── Step 3: parse ─────────────────────────────────────────────────────
        try:
            parser = get_parser(mime_type)
            extracted = parser(file_content, filename)
        except Exception as exc:
            raise _PermanentTaskError(f"Failed to extract text: {exc}") from exc

        page_count = extracted.get("page_count")
        word_count = extracted.get("word_count")
        extraction_method = extracted.get("extraction_method")
        logger.info("Extracted %s words from %s", word_count, filename)

        # ── Step 4: chunk ─────────────────────────────────────────────────────
        # Chunk per page (not the whole document as one blob) so each chunk
        # carries an accurate page_number for citations — for single-page
        # documents (CSV/text/image/most PDFs) this is identical to chunking
        # extracted["text"] directly, since that's just the pages joined.
        config = ChunkingConfig()
        pages = extracted.get("pages") or [{"page_number": None, "text": extracted.get("text", "")}]
        chunks: list = []
        for page in pages:
            chunks.extend(chunk_text(page["text"], config, page_number=page.get("page_number")))
        for i, chunk in enumerate(chunks):
            chunk["chunk_index"] = i

        logger.info("Created %d chunks from %s", len(chunks), filename)

        # ── Steps 5-6: store chunks, mark ready, audit log (one transaction) ──
        async with session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                raise _DocumentNotFound(str(document_id))

            doc.page_count = page_count
            doc.word_count = word_count
            doc.extraction_method = extraction_method

            # Delete any existing chunks (reprocessing case), then batch insert.
            await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

            rows = [
                {
                    "id": uuid.uuid4(),
                    "document_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    "content": chunk["content"],
                    "chunk_type": ChunkType(chunk["chunk_type"]),
                    "token_count": chunk["token_count"],
                    "page_number": chunk["metadata"]["page_number"],
                    # embedding/embedding_model/embedding_generated_at left
                    # NULL — generate_embeddings fills these in as a
                    # separate, independently retryable step chained below.
                }
                for chunk in chunks
            ]
            for i in range(0, len(rows), _CHUNK_INSERT_BATCH_SIZE):
                batch = rows[i:i + _CHUNK_INSERT_BATCH_SIZE]
                if batch:
                    await db.execute(insert(DocumentChunk), batch)

            doc.status = DocumentStatus.ready
            doc.embedding_status = "pending"
            doc.chunk_count = len(chunks)

            db.add(AuditLog(
                id=uuid.uuid4(),
                user_id=doc.uploaded_by,
                action="document.processed",
                resource_type="document",
                resource_id=document_id,
                meta={
                    "word_count": word_count,
                    "chunk_count": len(chunks),
                    "page_count": page_count,
                    "extraction_method": extraction_method,
                },
            ))

            await db.commit()

        logger.info("Parsing complete for %s — %d chunks ready for embedding", filename, len(chunks))

        # Hand off to the embedding stage as a separate, independently
        # retryable task — a transient embedding hiccup shouldn't force a
        # full re-parse, and a large document's embedding step shouldn't
        # hold this task's S3/parser resources open.
        generate_embeddings.delay(str(document_id))
    finally:
        await engine.dispose()


async def _run_embed(document_id: uuid.UUID) -> None:
    engine, session_factory = _make_session_factory()
    try:
        # ── Step 1: load and validate ─────────────────────────────────────────
        async with session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                logger.error("document %s not found — nothing to embed", document_id)
                raise _DocumentNotFound(str(document_id))

            if doc.status != DocumentStatus.ready:
                logger.warning(
                    "generate_embeddings called for document %s with status=%s "
                    "(expected 'ready') — skipping",
                    document_id, doc.status.value,
                )
                return
            if not doc.chunk_count:
                logger.warning(
                    "generate_embeddings called for document %s with no chunks — skipping", document_id
                )
                return

            filename = doc.filename
            doc.embedding_status = "generating"
            await db.commit()

        logger.info("Embedding started for %s", filename)

        # ── Step 2: fetch chunks in batches (resumable) ─────────────────────────
        async with session_factory() as db:
            progress = await ChunkRepository(db).get_embedding_progress(document_id)

        total_chunks = progress["total_chunks"]
        embedded_so_far = progress["embedded_chunks"]
        if embedded_so_far:
            # Step 3: chunks already embedded from an earlier, interrupted
            # attempt are never re-embedded — get_chunks_without_embeddings
            # only returns rows where embedding IS NULL, so resuming is
            # automatic rather than something this loop has to detect itself.
            logger.info(
                "Resuming embedding for %s — %d/%d chunks already embedded from a prior attempt",
                filename, embedded_so_far, total_chunks,
            )

        async with session_factory() as db:
            result = await db.execute(
                select(DocumentChunk.content)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
            all_contents = [row[0] for row in result.all()]

        cost = estimate_embedding_cost(all_contents)
        logger.info(
            "Embedding cost estimate for %s: %d tokens across %d chunks, $%.5f",
            filename, cost["total_tokens"], cost["chunk_count"], cost["estimated_cost_usd"],
        )

        async with session_factory() as db:
            repo = ChunkRepository(db)
            while True:
                batch = await repo.get_chunks_without_embeddings(document_id, batch_size=_EMBED_BATCH_SIZE)
                if not batch:
                    break

                try:
                    vectors = generate_embeddings_batch(
                        [c.content for c in batch],
                        chunk_ids=[str(c.id) for c in batch],
                    )
                except Exception as exc:
                    raise RuntimeError("Failed to generate embeddings") from exc

                await repo.save_embeddings_batch([
                    {"chunk_id": c.id, "embedding": vector, "model_name": settings.embedding_model}
                    for c, vector in zip(batch, vectors)
                ])

                embedded_so_far += len(batch)
                logger.info("Embedded %d/%d chunks for %s", embedded_so_far, total_chunks, filename)

                # No inter-batch delay: the original request for one asked
                # for "rate limit protection", which only makes sense for a
                # hosted API with a requests-per-minute cap. Local inference
                # has no such limit, so pausing here would just slow down
                # indexing for no benefit.

        # ── Step 4: finalize ─────────────────────────────────────────────────
        async with session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                raise _DocumentNotFound(str(document_id))

            doc.status = DocumentStatus.indexed
            doc.embedding_status = "complete"
            doc.processing_completed_at = datetime.now(timezone.utc)

            monitored_cost_usd = (cost["total_tokens"] / 1000) * settings.embedding_cost_per_1k_tokens_usd

            db.add(AuditLog(
                id=uuid.uuid4(),
                user_id=doc.uploaded_by,
                action="document.indexed",
                resource_type="document",
                resource_id=document_id,
                meta={
                    "chunk_count": total_chunks,
                    "tokens_used": cost["total_tokens"],
                    "estimated_cost_usd": cost["estimated_cost_usd"],
                    "embedding_model": settings.embedding_model,
                },
            ))
            db.add(EmbeddingCost(
                id=uuid.uuid4(),
                document_id=document_id,
                user_id=doc.uploaded_by,
                chunk_count=total_chunks,
                token_count=cost["total_tokens"],
                model_name=settings.embedding_model,
                cost_usd=monitored_cost_usd,
            ))
            await db.commit()

        logger.info(
            "Embedding complete for %s — %d chunks embedded, %d tokens, $%.5f estimated cost",
            filename, total_chunks, cost["total_tokens"], cost["estimated_cost_usd"],
        )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: str) -> None:
    doc_id = uuid.UUID(document_id)
    try:
        asyncio.run(_run_parse(doc_id))
    except _DocumentNotFound:
        return
    except _PermanentTaskError as exc:
        logger.error("Permanent failure processing document %s: %s", document_id, exc)
        asyncio.run(_mark_error(doc_id, str(exc)))
    except Exception as exc:
        logger.error(
            "Processing failed for document %s (attempt %d/%d): %s",
            document_id, self.request.retries + 1, self.max_retries + 1, exc,
        )
        asyncio.run(_mark_error(doc_id, str(exc)))
        if self.request.retries >= self.max_retries:
            logger.error(
                "Document %s permanently failed after exhausting retries — "
                "error notification would be sent here (email in Session 18)",
                document_id,
            )
            return
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


# No rate_limit here: the original spec's rate_limit='10/m' and inter-batch
# sleep both model a hosted embeddings API's requests-per-minute cap. This
# project uses a local model with no external rate limit, so either would
# only throttle indexing for no reason — e.g. capping this at 10 documents/
# minute regardless of how many are queued during a bulk upload.
@celery_app.task(bind=True, max_retries=3)
def generate_embeddings(self, document_id: str) -> None:
    doc_id = uuid.UUID(document_id)
    try:
        asyncio.run(_run_embed(doc_id))
    except _DocumentNotFound:
        return
    except Exception as exc:
        # No OpenAI 429/rate-limit branch: there's no hosted API in this
        # pipeline, so every failure gets the same generic retry-with-backoff
        # treatment process_document already uses.
        logger.error(
            "Embedding failed for document %s (attempt %d/%d): %s",
            document_id, self.request.retries + 1, self.max_retries + 1, exc,
        )
        asyncio.run(_mark_embedding_error(doc_id, str(exc)))
        if self.request.retries >= self.max_retries:
            logger.error(
                "Document %s permanently failed to embed after exhausting retries — "
                "parsed content remains available, but it won't be searchable until retried.",
                document_id,
            )
            return
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))