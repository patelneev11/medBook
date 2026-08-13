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


# ── Agent ─────────────────────────────────────────────────────────────────────


class AgentQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    project_id: Optional[uuid.UUID] = None
    conversation_id: Optional[uuid.UUID] = None
    stream: bool = True


class AgentCitation(BaseModel):
    document_id: uuid.UUID
    document_name: str
    page_number: Optional[int] = None
    excerpt: str


class AgentToolCall(BaseModel):
    tool: str
    message: str
    found: str
    execution_time_ms: int


class AgentQueryResponse(BaseModel):
    query_id: uuid.UUID
    conversation_id: uuid.UUID
    question: str
    answer: str
    citations: list[AgentCitation]
    tool_calls: list[AgentToolCall]
    iterations: int
    documents_accessed: list[uuid.UUID]
    tokens_used: int
    response_time_ms: int
    truncated: bool = False
