import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import AppException
from ..models.chunk import DocumentChunk
from ..models.document import Document, DocumentStatus
from ..models.user import User
from ..schemas.document import (
    ChunkResponse,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUpdate,
)
from ..schemas.search import SimilarDocumentItem, SimilarDocumentsResponse
from ..services import file_validator
from ..services import storage as storage_service
from ..services.search import find_similar_documents
from tasks.document_tasks import generate_embeddings, process_document

logger = logging.getLogger("mednotebook.documents")

router = APIRouter(prefix="/documents", tags=["documents"])

# Auth is not yet implemented — all operations use this placeholder owner.
_PLACEHOLDER_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")

_SUPPORTED_TYPES = ", ".join(sorted(file_validator.ALLOWED_TYPES.keys()))
_TEXT_PREVIEW_CHARS = 500

# No per-step progress instrumentation yet — coarse mapping until the real
# extraction pipeline reports granular progress. "ready" is a real
# in-progress state now (parsed, embeddings not generated yet), not a
# synonym for done — only "indexed" means fully done.
_PROGRESS_BY_STATUS = {
    DocumentStatus.pending: 0,
    DocumentStatus.processing: 50,
    DocumentStatus.ready: 75,
    DocumentStatus.indexed: 100,
    DocumentStatus.error: 0,
}


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    project_id: Optional[uuid.UUID] = None,
    doc_status: Optional[DocumentStatus] = Query(None, alias="status"),
    mime_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    conditions = [Document.uploaded_by == _PLACEHOLDER_USER]
    if project_id is not None:
        conditions.append(Document.project_id == project_id)
    if doc_status is not None:
        conditions.append(Document.status == doc_status)
    if mime_type is not None:
        conditions.append(Document.mime_type == mime_type)

    stmt = (
        select(Document)
        .where(and_(*conditions))
        .order_by(Document.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    display_name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    original_filename = file.filename or "upload"
    mime_type = file.content_type or "application/octet-stream"

    # 1. Read file into memory
    content = await file.read()

    # 2. Validate — raises AppException on failure (413 / 415 / 400)
    try:
        file_validator.validate_file(original_filename, mime_type, len(content))
    except AppException as exc:
        if exc.code == "UNSUPPORTED_FILE_TYPE":
            raise AppException(
                f"File type not supported. Accepted types: {_SUPPORTED_TYPES}",
                "UNSUPPORTED_FILE_TYPE",
                415,
            ) from exc
        raise

    # 3. Sanitize filename
    safe_filename = file_validator.sanitize_filename(original_filename)

    # 4. Create pending DB record
    parsed_project_id = uuid.UUID(project_id) if project_id else None
    doc = Document(
        id=uuid.uuid4(),
        uploaded_by=_PLACEHOLDER_USER,
        project_id=parsed_project_id,
        filename=safe_filename,
        display_name=display_name or original_filename,
        file_key=f"pending/{uuid.uuid4()}",  # replaced after S3 upload
        mime_type=mime_type,
        status=DocumentStatus.pending,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # 5. Upload to S3
    try:
        s3_result = storage_service.upload_file(
            file_content=content,
            filename=safe_filename,
            mime_type=mime_type,
            user_id=str(_PLACEHOLDER_USER),
        )
    except AppException:
        doc.status = DocumentStatus.error
        await db.commit()
        raise AppException(
            "File upload failed. Please try again later.",
            "S3_UPLOAD_FAILED",
            500,
        )

    # 6. Update with real S3 key and size
    doc.file_key = s3_result["file_key"]
    doc.file_size_bytes = s3_result["file_size_bytes"]
    doc.status = DocumentStatus.processing
    await db.commit()
    await db.refresh(doc)

    # 7. Enqueue text extraction — picked up by a Celery worker via Redis
    process_document.delay(str(doc.id))

    return doc


# ── Single document ───────────────────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await _get_or_404(document_id, db)

    uploader_name = None
    user_result = await db.execute(select(User.full_name).where(User.id == doc.uploaded_by))
    uploader_name = user_result.scalar_one_or_none()

    preview = None
    embedded_chunk_count = None
    embedding_model = None
    if doc.status in (DocumentStatus.ready, DocumentStatus.indexed):
        chunk_result = await db.execute(
            select(DocumentChunk.content)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .limit(1)
        )
        first_chunk_content = chunk_result.scalar_one_or_none()
        if first_chunk_content:
            preview = first_chunk_content[:_TEXT_PREVIEW_CHARS]

        progress_result = await db.execute(
            select(
                func.count(DocumentChunk.embedding),  # COUNT ignores NULLs
                func.max(DocumentChunk.embedding_model),
            ).where(DocumentChunk.document_id == document_id)
        )
        embedded_chunk_count, embedding_model = progress_result.one()

    return DocumentDetailResponse(
        **DocumentResponse.model_validate(doc).model_dump(),
        uploaded_by_name=uploader_name,
        extracted_text_preview=preview,
        embedded_chunk_count=embedded_chunk_count,
        embedding_model=embedding_model,
    )


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await _get_or_404(document_id, db)
    return DocumentStatusResponse(
        id=doc.id,
        status=doc.status,
        embedding_status=doc.embedding_status,
        progress_percent=_PROGRESS_BY_STATUS[doc.status],
        error_message=doc.error_message,
        word_count=doc.word_count,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
    )


@router.post("/{document_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await _get_or_404(document_id, db)

    # Two distinct failure points can now land here: parsing itself failed
    # (status=error — needs a full re-parse), or parsing succeeded but
    # embedding permanently failed (status stays "ready", embedding_status
    # ="error" — only the embedding step needs retrying, not a re-parse).
    embedding_only_retry = doc.status == DocumentStatus.ready and doc.embedding_status == "error"
    if doc.status != DocumentStatus.error and not embedding_only_retry:
        raise AppException(
            "Only documents with status 'error', or 'ready' with a failed embedding step, can be retried",
            "INVALID_STATUS_FOR_RETRY",
            400,
        )

    if embedding_only_retry:
        doc.embedding_status = "pending"
        await db.commit()
        generate_embeddings.delay(str(doc.id))
        return {"message": "Embedding generation restarted"}

    if doc.file_key.startswith("pending/"):
        raise AppException("File was never uploaded to storage — cannot retry", "FILE_NOT_READY", 400)

    doc.status = DocumentStatus.pending
    doc.error_message = None
    doc.processing_started_at = None
    doc.chunk_count = 0
    doc.embedding_status = "pending"

    await db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    await db.commit()

    process_document.delay(str(doc.id))
    return {"message": "Processing restarted"}


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdate,
    db: AsyncSession = Depends(get_db),
):
    doc = await _get_or_404(document_id, db)
    if payload.project_id is not None:
        doc.project_id = payload.project_id
    if payload.status is not None:
        doc.status = payload.status
    await db.commit()
    await db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await _get_or_404(document_id, db)
    if not doc.file_key.startswith("pending/"):
        storage_service.delete_file(doc.file_key)
    await db.delete(doc)
    await db.commit()


# ── Download / view ──────────────────────────────────────────────────────────

@router.get("/{document_id}/download")
async def download_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await _get_or_404(document_id, db)
    if doc.file_key.startswith("pending/"):
        raise AppException("File is not yet available for download", "FILE_NOT_READY", 400)
    url = storage_service.get_presigned_url(doc.file_key, expires_in=3600)
    return {"url": url, "expires_in": 3600}


@router.get("/{document_id}/view")
async def view_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    doc = await _get_or_404(document_id, db)
    if doc.file_key.startswith("pending/"):
        raise AppException("File is not yet available for viewing", "FILE_NOT_READY", 400)
    url = storage_service.get_presigned_url(doc.file_key, expires_in=300)
    return {"url": url, "expires_in": 300}


# ── Chunks ────────────────────────────────────────────────────────────────────

@router.get("/{document_id}/chunks", response_model=list[ChunkResponse])
async def list_chunks(
    document_id: uuid.UUID,
    limit: int = Query(10, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    await _get_or_404(document_id, db)
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .limit(limit)
    )
    return result.scalars().all()


# ── Similar documents ────────────────────────────────────────────────────────

@router.post("/{document_id}/similar", response_model=SimilarDocumentsResponse)
async def similar_documents(
    document_id: uuid.UUID,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    await _get_or_404(document_id, db)
    results = await find_similar_documents(db, str(document_id), str(_PLACEHOLDER_USER), limit=limit)
    return SimilarDocumentsResponse(documents=[SimilarDocumentItem(**r) for r in results])


# ── Summarize ─────────────────────────────────────────────────────────────────

@router.post("/{document_id}/summarize", status_code=status.HTTP_202_ACCEPTED)
async def summarize_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _get_or_404(document_id, db)
    # TODO: enqueue background summarization task — Session 6
    return {"message": "Summarization queued", "document_id": str(document_id)}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_or_404(document_id: uuid.UUID, db: AsyncSession) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise AppException("Document not found", "DOCUMENT_NOT_FOUND", 404)
    return doc
