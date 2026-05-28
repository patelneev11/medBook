import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.document import DocumentStatus
from ..schemas.document import ChunkResponse, DocumentResponse, DocumentUpdate

router = APIRouter(prefix="/documents", tags=["documents"])

_PLACEHOLDER_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _placeholder_doc(
    document_id: uuid.UUID,
    filename: str = "document.pdf",
    mime_type: str = "application/pdf",
    project_id: uuid.UUID | None = None,
) -> DocumentResponse:
    now = _now()
    return DocumentResponse(
        id=document_id,
        uploaded_by=_PLACEHOLDER_USER,
        project_id=project_id,
        filename=filename,
        file_key=f"uploads/{document_id}/{filename}",
        file_size_bytes=None,
        mime_type=mime_type,
        status=DocumentStatus.pending,
        page_count=None,
        word_count=None,
        summary=None,
        created_at=now,
        updated_at=now,
    )


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    project_id: uuid.UUID | None = None,
    doc_status: DocumentStatus | None = None,
    mime_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    # TODO: query DB with filters, filter by authenticated user — Session 4/5
    return []


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    project_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    # TODO: upload to S3, extract text, chunk, embed — Session 5
    parsed_project_id = uuid.UUID(project_id) if project_id else None
    new_id = uuid.uuid4()
    return _placeholder_doc(
        document_id=new_id,
        filename=file.filename or "upload",
        mime_type=file.content_type or "application/octet-stream",
        project_id=parsed_project_id,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # TODO: load from DB — Session 5
    return _placeholder_doc(document_id=document_id)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: uuid.UUID, payload: DocumentUpdate, db: AsyncSession = Depends(get_db)
):
    # TODO: update in DB — Session 5
    return _placeholder_doc(document_id=document_id, project_id=payload.project_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # TODO: delete document and its chunks from DB and S3 — Session 5
    pass


@router.get("/{document_id}/chunks", response_model=list[ChunkResponse])
async def list_chunks(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # TODO: load chunks from DB — Session 5
    return []


@router.post("/{document_id}/summarize", status_code=status.HTTP_202_ACCEPTED)
async def summarize_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # TODO: enqueue background summarization task — Session 6
    return {"message": "Summarization queued", "document_id": str(document_id)}
