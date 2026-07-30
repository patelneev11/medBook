import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mednotebook_backend.config import settings
from mednotebook_backend.database import async_url
from mednotebook_backend.exceptions import AppException
from mednotebook_backend.models.document import Document, DocumentStatus
from mednotebook_backend.services import storage as storage_service
from mednotebook_backend.services.parsers import ParserException, get_parser
from worker import celery_app

logger = logging.getLogger("mednotebook.tasks.document")


def _make_session_factory():
    # A fresh engine per call, not the FastAPI process's shared singleton —
    # see the note in _run(): asyncpg connections are bound to the event
    # loop that opened them, and every Celery task gets its own asyncio.run()
    # loop.
    engine = create_async_engine(async_url(settings.database_url), echo=False)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _set_status(document_id: uuid.UUID, status: DocumentStatus) -> None:
    engine, session_factory = _make_session_factory()
    try:
        async with session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                logger.warning("document %s not found — skipping status update", document_id)
                return
            doc.status = status
            await db.commit()
    finally:
        await engine.dispose()


async def _run(document_id: uuid.UUID) -> None:
    engine, session_factory = _make_session_factory()
    try:
        logger.info("Starting processing for document %s", document_id)

        async with session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                logger.warning("document %s not found — aborting", document_id)
                return
            doc.status = DocumentStatus.processing
            await db.commit()
            file_key, mime_type, filename = doc.file_key, doc.mime_type, doc.filename

        parser = get_parser(mime_type)
        file_content = storage_service.download_file(file_key)
        extracted = parser(file_content, filename)
        page_count = extracted["page_count"]
        word_count = extracted["word_count"]
        logger.info(
            "Extracted %d words across %d pages from document %s (%s)",
            word_count, page_count, document_id, extracted["extraction_method"],
        )

        async with session_factory() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalar_one_or_none()
            if doc is None:
                return
            if page_count is not None:
                doc.page_count = page_count
            if word_count is not None:
                doc.word_count = word_count
            doc.status = DocumentStatus.ready
            await db.commit()

        logger.info("Processing complete for document %s", document_id)
    finally:
        await engine.dispose()


@celery_app.task(bind=True, max_retries=3)
def process_document(self, document_id: str) -> None:
    doc_id = uuid.UUID(document_id)
    try:
        asyncio.run(_run(doc_id))
    except (ParserException, AppException) as exc:
        logger.error("Processing failed for document %s: %s", document_id, exc)
        if self.request.retries >= self.max_retries:
            asyncio.run(_set_status(doc_id, DocumentStatus.error))
            return
        raise self.retry(exc=exc, countdown=10)