import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

SearchTypeParam = Literal["semantic", "keyword", "hybrid"]
FileTypeParam = Literal["pdf", "csv", "excel", "image", "text"]
DateFilterParam = Literal["week", "month", "3months"]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    project_id: Optional[uuid.UUID] = None
    document_ids: Optional[list[uuid.UUID]] = None
    limit: int = Field(10, ge=1, le=50)
    search_type: SearchTypeParam = "semantic"
    # Not in the original endpoint spec — added so the frontend's file-type
    # and date filters actually constrain results server-side instead of
    # existing as UI that doesn't do anything.
    file_types: Optional[list[FileTypeParam]] = None
    date_filter: Optional[DateFilterParam] = None


class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    # Not in the original response spec — needed so the frontend can show
    # the "project name badge" the spec's result card also asks for.
    project_id: Optional[str]
    mime_type: Optional[str]
    content: str
    context_before: Optional[str]
    context_after: Optional[str]
    page_number: Optional[int]
    similarity_score: float
    chunk_type: Optional[str]


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    total_results: int
    search_type: SearchTypeParam
    search_time_ms: int


class SuggestionItem(BaseModel):
    type: Literal["recent_query", "document", "project"]
    text: str


class SuggestResponse(BaseModel):
    suggestions: list[SuggestionItem]


class SearchHistoryItem(BaseModel):
    id: uuid.UUID
    query: str
    result_count: int
    search_type: SearchTypeParam
    project_name: Optional[str]
    created_at: datetime


class SimilarDocumentItem(BaseModel):
    document_id: str
    document_name: str
    mime_type: Optional[str]
    similarity_score: float


class SimilarDocumentsResponse(BaseModel):
    documents: list[SimilarDocumentItem]