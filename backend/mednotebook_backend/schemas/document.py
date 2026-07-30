import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, computed_field, field_validator

from ..models.document import DocumentStatus
from ..services.file_validator import get_mime_type_label

_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class DocumentBase(BaseModel):
    filename: str
    display_name: Optional[str] = None
    mime_type: Optional[str] = None
    project_id: Optional[uuid.UUID] = None


class DocumentCreate(DocumentBase):
    file_size_bytes: Optional[int] = None

    @field_validator("file_size_bytes")
    @classmethod
    def validate_file_size(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v > _MAX_FILE_SIZE_BYTES:
            raise ValueError(f"file size must not exceed 50 MB ({_MAX_FILE_SIZE_BYTES} bytes)")
        return v


class DocumentUpdate(BaseModel):
    project_id: Optional[uuid.UUID] = None
    status: Optional[DocumentStatus] = None


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    uploaded_by: uuid.UUID
    file_key: str
    file_size_bytes: Optional[int]
    status: DocumentStatus
    page_count: Optional[int]
    word_count: Optional[int]
    summary: Optional[str]
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def file_type_label(self) -> str:
        return get_mime_type_label(self.mime_type or "")

    model_config = {"from_attributes": True}


class DocumentStatusResponse(BaseModel):
    id: uuid.UUID
    status: DocumentStatus
    progress_percent: int
    error_message: Optional[str] = None


# ── Chunks ────────────────────────────────────────────────────────────────────

class ChunkBase(BaseModel):
    content: str
    chunk_index: int
    page_number: Optional[int] = None
    token_count: Optional[int] = None


class ChunkResponse(ChunkBase):
    id: uuid.UUID
    document_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
