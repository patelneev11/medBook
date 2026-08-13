import json
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from ..database import AsyncSessionLocal, get_db
from ..exceptions import AppException
from ..models.query import AIQuery
from ..schemas.query import (
    AgentCitation,
    AgentQueryRequest,
    AgentQueryResponse,
    AgentToolCall,
    QueryCreate,
    QueryFeedbackRequest,
    QueryResponse,
)
from ..services.agent.orchestrator import AGENT_MODEL, AgentOrchestrator, AgentResponse

logger = logging.getLogger("mednotebook.agent")

router = APIRouter(prefix="/queries", tags=["queries"])
agent_router = APIRouter(prefix="/agent", tags=["agent"])

_PLACEHOLDER_USER = uuid.UUID("00000000-0000-0000-0000-000000000001")

# How many previous turns of a conversation are replayed to Claude. Each turn
# is a question + a full cited answer, so the window is capped to keep the
# system prompt + history well inside the context budget.
_HISTORY_TURNS = 10


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


# ── Agent ─────────────────────────────────────────────────────────────────────


@agent_router.post("/query")
async def agent_query(payload: AgentQueryRequest, db: AsyncSession = Depends(get_db)):
    """Ask the research agent a question.

    Streaming (the default) returns Server-Sent Events so the UI can show the
    agent's tool calls as they happen; `stream: false` returns the whole
    answer as JSON once the agent is done.
    """
    conversation_id = payload.conversation_id or uuid.uuid4()
    project_id = str(payload.project_id) if payload.project_id else None

    if payload.stream:
        return EventSourceResponse(
            _stream_agent(payload, conversation_id, project_id),
            # Nginx buffers SSE by default, which defeats the point.
            headers={"X-Accel-Buffering": "no"},
        )

    history = await _load_conversation_history(db, conversation_id)
    orchestrator = AgentOrchestrator(str(_PLACEHOLDER_USER), db)
    result = await orchestrator.run(payload.question, history, project_id)

    query = await _persist_turn(db, payload.question, payload.project_id, conversation_id, result)
    return _to_response(query, conversation_id, payload.question, result)


async def _stream_agent(
    payload: AgentQueryRequest, conversation_id: uuid.UUID, project_id: Optional[str]
) -> AsyncIterator[dict]:
    """SSE event source for one agent turn.

    Opens its own database session rather than using the route's: the request
    handler returns as soon as the response starts, so a dependency-scoped
    session may already be closing while this generator is still running.
    """
    async with AsyncSessionLocal() as db:
        try:
            yield _sse({"type": "start", "message": "Starting research..."})

            history = await _load_conversation_history(db, conversation_id)
            orchestrator = AgentOrchestrator(str(_PLACEHOLDER_USER), db)

            result: Optional[AgentResponse] = None
            async for event in orchestrator.stream(payload.question, history, project_id):
                if event["type"] == "final":
                    result = event["response"]
                    continue
                yield _sse(event)

            if result is None:  # unreachable — stream() always ends with "final"
                raise RuntimeError("agent stream ended without a final response")

            query = await _persist_turn(
                db, payload.question, payload.project_id, conversation_id, result
            )
            yield _sse(
                {
                    "type": "done",
                    "query_id": str(query.id),
                    "conversation_id": str(conversation_id),
                    "citations": [c.model_dump(mode="json") for c in _citations(result)],
                    "tool_calls": [t.model_dump(mode="json") for t in _tool_calls(result)],
                    "iterations": result.total_iterations,
                    "tokens_used": result.tokens_used,
                    "response_time_ms": result.response_time_ms,
                    "truncated": result.truncated,
                }
            )
        except Exception as exc:
            # The SSE stream has already started, so a raised exception would
            # just cut the connection with no explanation for the user.
            logger.exception("Agent stream failed")
            yield _sse(
                {
                    "type": "error",
                    "message": "The agent hit an error while researching this question.",
                    "detail": str(exc),
                }
            )


def _sse(event: dict) -> dict:
    return {"event": event["type"], "data": json.dumps(event)}


async def _load_conversation_history(db: AsyncSession, conversation_id: uuid.UUID) -> list[dict]:
    """Replay a conversation as Anthropic-format messages.

    Only question/answer text is replayed — not the tool_use blocks from
    previous turns. Those reference tool_use_ids that no longer have matching
    results in this request's message list, which the API rejects.
    """
    result = await db.execute(
        select(AIQuery)
        .where(
            AIQuery.conversation_id == conversation_id,
            AIQuery.user_id == _PLACEHOLDER_USER,
        )
        .order_by(AIQuery.created_at.desc())
        .limit(_HISTORY_TURNS)
    )
    turns = list(reversed(result.scalars().all()))

    messages: list[dict] = []
    for turn in turns:
        if not turn.answer:
            continue  # a turn that errored out — replaying it teaches nothing
        messages.append({"role": "user", "content": turn.question})
        messages.append({"role": "assistant", "content": turn.answer})
    return messages


async def _persist_turn(
    db: AsyncSession,
    question: str,
    project_id: Optional[uuid.UUID],
    conversation_id: uuid.UUID,
    result: AgentResponse,
) -> AIQuery:
    query = AIQuery(
        id=uuid.uuid4(),
        user_id=_PLACEHOLDER_USER,
        project_id=project_id,
        conversation_id=conversation_id,
        question=question,
        answer=result.answer,
        sources=[c.model_dump(mode="json") for c in _citations(result)],
        tool_calls=[t.model_dump(mode="json") for t in _tool_calls(result)],
        documents_accessed=list(result.documents_accessed),
        iterations=result.total_iterations,
        model_used=AGENT_MODEL,
        tokens_used=result.tokens_used,
        response_time_ms=result.response_time_ms,
    )
    db.add(query)
    await db.commit()
    await db.refresh(query)
    return query


def _citations(result: AgentResponse) -> list[AgentCitation]:
    return [
        AgentCitation(
            document_id=uuid.UUID(c.document_id),
            document_name=c.document_name,
            page_number=c.page_number,
            excerpt=c.excerpt,
        )
        for c in result.citations
    ]


def _tool_calls(result: AgentResponse) -> list[AgentToolCall]:
    return [
        AgentToolCall(
            tool=call.tool_name,
            message=call.input_summary,
            found=call.result_summary,
            execution_time_ms=call.execution_time_ms,
        )
        for call in result.tool_calls
    ]


def _to_response(
    query: AIQuery, conversation_id: uuid.UUID, question: str, result: AgentResponse
) -> AgentQueryResponse:
    return AgentQueryResponse(
        query_id=query.id,
        conversation_id=conversation_id,
        question=question,
        answer=result.answer,
        citations=_citations(result),
        tool_calls=_tool_calls(result),
        iterations=result.total_iterations,
        documents_accessed=[uuid.UUID(d) for d in result.documents_accessed],
        tokens_used=result.tokens_used,
        response_time_ms=result.response_time_ms,
        truncated=result.truncated,
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
