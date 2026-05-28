import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from ..models.document import DocumentStatus

_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class DocumentBase(BaseModel):
    filename: str
    mime_type: str | None = None
    project_id: uuid.UUID | None = None


class DocumentCreate(DocumentBase):
    file_size_bytes: int | None = None

    @field_validator("file_size_bytes")
    @classmethod
    def validate_file_size(cls, v: int | None) -> int | None:
        if v is not None and v > _MAX_FILE_SIZE_BYTES:
            raise ValueError(f"file size must not exceed 50 MB ({_MAX_FILE_SIZE_BYTES} bytes)")
        return v


class DocumentUpdate(BaseModel):
    project_id: uuid.UUID | None = None
    status: DocumentStatus | None = None


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    uploaded_by: uuid.UUID
    file_key: str
    file_size_bytes: int | None
    status: DocumentStatus
    page_count: int | None
    word_count: int | None
    summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Chunks ────────────────────────────────────────────────────────────────────

class ChunkBase(BaseModel):
    content: str
    chunk_index: int
    page_number: int | None = None
    token_count: int | None = None


class ChunkResponse(ChunkBase):
    id: uuid.UUID
    document_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
