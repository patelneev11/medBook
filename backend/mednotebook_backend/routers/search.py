import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..exceptions import AppException
from ..models.document import Document
from ..models.project import Project
from ..models.search_history import SearchHistory
from ..models.search_history import SearchType as SearchTypeEnum
from ..models.search_log import SearchLog
from ..schemas.search import (
    SearchHistoryItem,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SuggestionItem,
    SuggestResponse,
)
from ..services.search import hybrid_search, keyword_search, semantic_search

logger = logging.getLogger("mednotebook.search")

router = APIRouter(prefix="/search", tags=["search"])

# How many of the most recent search_logs rows to average when checking for
# a latency regression — one slow request shouldn't trip an alert, but a
# sustained trend across the last window should.
_PERFORMANCE_ALERT_WINDOW = 20
_SLOW_WARN_MS = 2000
_SLOW_ERROR_MS = 5000

# Auth is not yet implemented — same placeholder owner used throughout the
# rest of the API (see documents.py).
_PLACEHOLDER_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")

_SEARCH_FUNCTIONS = {
    "semantic": semantic_search,
    "keyword": keyword_search,
    "hybrid": hybrid_search,
}

_MIN_SUGGEST_CHARS = 3

# Frontend filter categories -> the real mime types each one covers.
_FILE_TYPE_MIME_TYPES: dict[str, list[str]] = {
    "pdf": ["application/pdf"],
    "csv": ["text/csv"],
    "excel": [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    ],
    "image": ["image/jpeg", "image/png", "image/tiff"],
    "text": ["text/plain", "text/markdown", "application/json"],
}

_DATE_FILTER_DELTAS: dict[str, timedelta] = {
    "week": timedelta(days=7),
    "month": timedelta(days=30),
    "3months": timedelta(days=90),
}


def _resolve_mime_types(file_types: Optional[list[str]]) -> Optional[list[str]]:
    if not file_types:
        return None
    mime_types: list[str] = []
    for category in file_types:
        mime_types.extend(_FILE_TYPE_MIME_TYPES[category])
    return mime_types


def _resolve_since(date_filter: Optional[str]) -> Optional[datetime]:
    if date_filter is None:
        return None
    return datetime.now(timezone.utc) - _DATE_FILTER_DELTAS[date_filter]


async def _check_search_performance(db: AsyncSession) -> None:
    """Warn/error when recent search latency drifts up — a sustained rise
    here means the pgvector index needs tuning (or a rebuild as the corpus
    grows), not that any single request is a problem.
    """
    recent = (
        select(SearchLog.search_time_ms)
        .order_by(SearchLog.created_at.desc())
        .limit(_PERFORMANCE_ALERT_WINDOW)
        .subquery()
    )
    result = await db.execute(select(func.avg(recent.c.search_time_ms)))
    avg_ms = result.scalar()
    if avg_ms is None:
        return
    if avg_ms > _SLOW_ERROR_MS:
        logger.error(
            "Average search time over the last %d searches is %.0fms (> %dms) — "
            "pgvector index needs tuning",
            _PERFORMANCE_ALERT_WINDOW, avg_ms, _SLOW_ERROR_MS,
        )
    elif avg_ms > _SLOW_WARN_MS:
        logger.warning(
            "Average search time over the last %d searches is %.0fms (> %dms)",
            _PERFORMANCE_ALERT_WINDOW, avg_ms, _SLOW_WARN_MS,
        )


@router.post("", response_model=SearchResponse)
async def search(payload: SearchRequest, db: AsyncSession = Depends(get_db)):
    user_id = _PLACEHOLDER_USER

    # "Verify access" — meaningful once real multi-user auth exists. Today
    # there's exactly one user and everything belongs to it, so this mostly
    # guards against a project_id/document_ids that don't actually belong
    # to the requester, rather than something that can fire in practice yet.
    if payload.project_id is not None:
        result = await db.execute(select(Project).where(Project.id == payload.project_id))
        project = result.scalar_one_or_none()
        if project is not None and project.owner_id != user_id:
            raise AppException("You do not have access to this project", "PROJECT_ACCESS_DENIED", 403)

    if payload.document_ids:
        result = await db.execute(
            select(Document.id).where(
                Document.id.in_(payload.document_ids), Document.uploaded_by == user_id
            )
        )
        accessible = {row[0] for row in result.all()}
        missing = set(payload.document_ids) - accessible
        if missing:
            raise AppException(
                f"No access to document(s): {', '.join(str(d) for d in missing)}",
                "DOCUMENT_ACCESS_DENIED",
                403,
            )

    search_fn = _SEARCH_FUNCTIONS[payload.search_type]

    started = time.perf_counter()
    results = await search_fn(
        db,
        payload.query,
        str(user_id),
        project_id=str(payload.project_id) if payload.project_id else None,
        document_ids=[str(d) for d in payload.document_ids] if payload.document_ids else None,
        limit=payload.limit,
        since=_resolve_since(payload.date_filter),
        mime_types=_resolve_mime_types(payload.file_types),
    )
    search_time_ms = int((time.perf_counter() - started) * 1000)

    db.add(SearchHistory(
        id=uuid.uuid4(),
        user_id=user_id,
        project_id=payload.project_id,
        query_text=payload.query,
        search_type=SearchTypeEnum(payload.search_type),
        result_count=len(results),
    ))
    # Hashed, not plain text — this table is for aggregate monitoring
    # (content gaps, semantic-vs-hybrid comparison, latency), not display,
    # so there's no reason to retain the raw query here.
    query_hash = hashlib.sha256(payload.query.encode("utf-8")).hexdigest()
    db.add(SearchLog(
        id=uuid.uuid4(),
        user_id=user_id,
        project_id=payload.project_id,
        query_hash=query_hash,
        search_type=SearchTypeEnum(payload.search_type),
        result_count=len(results),
        search_time_ms=search_time_ms,
        had_results=len(results) > 0,
    ))
    await db.commit()

    await _check_search_performance(db)

    return SearchResponse(
        query=payload.query,
        results=[
            SearchResultItem(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                document_name=r.document_name,
                project_id=r.project_id,
                mime_type=r.mime_type,
                content=r.content,
                context_before=r.context_before,
                context_after=r.context_after,
                page_number=r.page_number,
                similarity_score=r.similarity_score,
                chunk_type=r.chunk_type,
            )
            for r in results
        ],
        total_results=len(results),
        search_type=payload.search_type,
        search_time_ms=search_time_ms,
    )


@router.get("/suggest", response_model=SuggestResponse)
async def suggest(
    q: str = Query(""),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    user_id = _PLACEHOLDER_USER
    q = q.strip()
    if len(q) < _MIN_SUGGEST_CHARS:
        return SuggestResponse(suggestions=[])

    suggestions: list[SuggestionItem] = []

    # Recent queries this user has typed that start with q — cheap ILIKE,
    # no embedding call, so this stays fast enough for autocomplete.
    result = await db.execute(
        select(SearchHistory.query_text)
        .where(SearchHistory.user_id == user_id, SearchHistory.query_text.ilike(f"{q}%"))
        .order_by(SearchHistory.created_at.desc())
        .limit(3)
    )
    seen: set[str] = set()
    for (text,) in result.all():
        if text not in seen:
            seen.add(text)
            suggestions.append(SuggestionItem(type="recent_query", text=text))

    like_pattern = f"%{q}%"

    remaining = limit - len(suggestions)
    if remaining > 0:
        doc_result = await db.execute(
            select(func.coalesce(Document.display_name, Document.filename))
            .where(
                Document.uploaded_by == user_id,
                or_(Document.filename.ilike(like_pattern), Document.display_name.ilike(like_pattern)),
            )
            .limit(remaining)
        )
        for (name,) in doc_result.all():
            suggestions.append(SuggestionItem(type="document", text=name))

    remaining = limit - len(suggestions)
    if remaining > 0:
        proj_result = await db.execute(
            select(Project.name)
            .where(Project.owner_id == user_id, Project.name.ilike(like_pattern))
            .limit(remaining)
        )
        for (name,) in proj_result.all():
            suggestions.append(SuggestionItem(type="project", text=name))

    return SuggestResponse(suggestions=suggestions[:limit])


@router.get("/history", response_model=list[SearchHistoryItem])
async def history(db: AsyncSession = Depends(get_db)):
    user_id = _PLACEHOLDER_USER
    result = await db.execute(
        select(SearchHistory, Project.name)
        .outerjoin(Project, SearchHistory.project_id == Project.id)
        .where(SearchHistory.user_id == user_id)
        .order_by(SearchHistory.created_at.desc())
        .limit(20)
    )
    return [
        SearchHistoryItem(
            id=entry.id,
            query=entry.query_text,
            result_count=entry.result_count,
            search_type=entry.search_type.value,
            project_name=project_name,
            created_at=entry.created_at,
        )
        for entry, project_name in result.all()
    ]


@router.delete("/history", status_code=204)
async def clear_history(db: AsyncSession = Depends(get_db)):
    # Not in the original endpoint list — added because the frontend's
    # "Clear history" link needs something real to call.
    await db.execute(delete(SearchHistory).where(SearchHistory.user_id == _PLACEHOLDER_USER))
    await db.commit()