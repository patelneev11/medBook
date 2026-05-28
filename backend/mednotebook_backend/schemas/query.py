import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class QueryBase(BaseModel):
    question: str = Field(..., min_length=1)
    project_id: uuid.UUID | None = None


class QueryCreate(QueryBase):
    pass


class QueryUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    project_id: uuid.UUID | None = None


class QueryResponse(QueryBase):
    id: uuid.UUID
    user_id: uuid.UUID
    answer: str | None
    sources: list | None
    model_used: str
    tokens_used: int | None
    response_time_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
