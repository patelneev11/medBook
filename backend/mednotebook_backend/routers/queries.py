import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..schemas.query import QueryCreate, QueryResponse

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
