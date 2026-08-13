import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class QueryBase(BaseModel):
    question: str = Field(..., min_length=1)
    project_id: Optional[uuid.UUID] = None


class QueryCreate(QueryBase):
    pass


class QueryUpdate(BaseModel):
    question: Optional[str] = Field(default=None, min_length=1)
    project_id: Optional[uuid.UUID] = None


class QueryResponse(QueryBase):
    id: uuid.UUID
    user_id: uuid.UUID
    answer: Optional[str]
    sources: Optional[list]
    model_used: str
    tokens_used: Optional[int]
    response_time_ms: Optional[int]
    search_log_id: Optional[uuid.UUID] = None
    helpful: Optional[bool] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class QueryFeedbackRequest(BaseModel):
    helpful: bool
