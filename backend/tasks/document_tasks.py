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
from mednotebook_backend.services import storage as storage_service
from mednotebook_backend.services.chunker import ChunkingConfig, chunk_text
from mednotebook_backend.services.parsers import get_parser
from worker import celery_app

logger = logging.getLogger("mednotebook.tasks.document")

_CHUNK_INSERT_BATCH_SIZE = 100


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
            await db.commit()
    finally:
        await engine.dispose()


async def _run(document_id: uuid.UUID) -> None:
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
            file_key, mime_type, filename, uploaded_by = doc.file_key, doc.mime_type, doc.filename, doc.uploaded_by

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

        # ── Steps 5-7: store chunks, update status, audit log (one transaction) ──
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
                    # embedding left NULL — Session 6 fills this in
                }
                for chunk in chunks
            ]
            for i in range(0, len(rows), _CHUNK_INSERT_BATCH_SIZE):
                batch = rows[i:i + _CHUNK_INSERT_BATCH_SIZE]
                if batch:
                    await db.execute(insert(DocumentChunk), batch)

            doc.status = DocumentStatus.ready
            doc.processing_completed_at = datetime.now(timezone.utc)
            doc.chunk_count = len(chunks)

            db.add(AuditLog(
                id=uuid.uuid4(),
                user_id=uploaded_by,
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

        logger.info(
            "Processing complete for %s — %d chunks ready for embedding",
            filename, len(chunks),
        )
    finally:
        await engine.dispose()


@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: str) -> None:
    doc_id = uuid.UUID(document_id)
    try:
        asyncio.run(_run(doc_id))
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