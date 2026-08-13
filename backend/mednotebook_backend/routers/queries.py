import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import AppException
from ..models.query import AIQuery
from ..schemas.query import QueryCreate, QueryFeedbackRequest, QueryResponse

router = APIRouter(prefix="/queries", tags=["queries"])

_PLACEHOLDER_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("", response_model=QueryResponse, status_code=status.HTTP_201_CREATED)
async def create_query(payload: QueryCreate, db: AsyncSession = Depends(get_db)):
    # TODO: run RAG pipeline — Session 6
    return QueryResponse(
        id=uuid.uuid4(),
        user_id=_PLACEHOLDER_USER,
        project_id=payload.project_id,
        question=payload.question,
        answer=None,
        sources=None,
        model_used="claude-sonnet-4-20250514",
        tokens_used=None,
        response_time_ms=None,
        created_at=_now(),
    )


@router.patch("/{query_id}/feedback", response_model=QueryResponse)
async def submit_feedback(
    query_id: uuid.UUID, payload: QueryFeedbackRequest, db: AsyncSession = Depends(get_db)
):
    # Query/list/get above don't persist yet (Session 6's TODOs) — this
    # endpoint operates on real ai_queries rows, ready for once that lands,
    # so it 404s until then rather than pretending to rate something that
    # was never saved.
    result = await db.execute(select(AIQuery).where(AIQuery.id == query_id))
    query = result.scalar_one_or_none()
    if query is None:
        raise AppException("Query not found", "QUERY_NOT_FOUND", 404)

    query.helpful = payload.helpful
    await db.commit()
    await db.refresh(query)

    return QueryResponse(
        id=query.id,
        user_id=query.user_id,
        project_id=query.project_id,
        question=query.question,
        answer=query.answer,
        sources=query.sources,
        model_used=query.model_used,
        tokens_used=query.tokens_used,
        response_time_ms=query.response_time_ms,
        search_log_id=query.search_log_id,
        helpful=query.helpful,
        created_at=query.created_at,
    )


@router.get("", response_model=list[QueryResponse])
async def list_queries(db: AsyncSession = Depends(get_db)):
    # TODO: filter by authenticated user — Session 4
    return []


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query(query_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    # TODO: load from DB — Session 4
    return QueryResponse(
        id=query_id,
        user_id=_PLACEHOLDER_USER,
        project_id=None,
        question="Placeholder question",
        answer=None,
        sources=None,
        model_used="claude-sonnet-4-20250514",
        tokens_used=None,
        response_time_ms=None,
        created_at=_now(),
    )
