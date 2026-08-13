"""Integration tests for POST /api/v1/agent/query.

The Anthropic client is stubbed — these cover our wiring (SSE framing, event
order, persistence, conversation threading), not Claude itself.
"""

import json
import types
import uuid

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import delete, select
from sse_starlette.sse import AppStatus

from mednotebook_backend.database import AsyncSessionLocal, engine
from mednotebook_backend.main import app
from mednotebook_backend.models.document import Document, DocumentStatus
from mednotebook_backend.models.project import Project
from mednotebook_backend.models.query import AIQuery
from mednotebook_backend.models.user import User
from mednotebook_backend.services.agent import orchestrator as orchestrator_module

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ANSWER = "Mean glucose was 126 mg/dL [Q3_cohort.csv]."


class _Block:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _Message:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = types.SimpleNamespace(input_tokens=100, output_tokens=50)


class _FakeMessages:
    """Two turns: one tool call, then the final cited answer."""

    def __init__(self):
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return _Message(
                [
                    _Block(type="text", text="Let me check your documents."),
                    _Block(type="tool_use", id="t1", name="get_document_list", input={}),
                ],
                "tool_use",
            )
        return _Message([_Block(type="text", text=ANSWER)], "end_turn")


@pytest.fixture(autouse=True)
def fake_anthropic(monkeypatch):
    fake = _FakeMessages()
    monkeypatch.setattr(
        orchestrator_module.anthropic,
        "AsyncAnthropic",
        lambda **kwargs: types.SimpleNamespace(messages=fake),
    )
    return fake


@pytest.fixture(autouse=True)
def reset_sse_exit_event():
    """sse-starlette caches a process-global shutdown Event on first use; it
    stays bound to the loop of the test that created it. Only an issue under
    pytest's one-loop-per-test, not in a real server.
    """
    AppStatus.should_exit_event = None


@pytest_asyncio.fixture(autouse=True)
async def fresh_engine():
    """asyncpg connections belong to the loop that opened them, and
    pytest-asyncio gives every test a new loop — dispose the app's shared
    engine between tests so pooled connections are never reused across loops.
    """
    yield
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def seed():
    async with AsyncSessionLocal() as db:
        await db.execute(delete(AIQuery).where(AIQuery.user_id == USER_ID))
        await db.execute(delete(Document).where(Document.uploaded_by == USER_ID))
        if (await db.execute(select(User).where(User.id == USER_ID))).scalar_one_or_none() is None:
            db.add(
                User(
                    id=USER_ID,
                    email="agent-test@example.com",
                    full_name="Agent Test",
                    hashed_password="x",
                )
            )
        db.add(
            Document(
                id=uuid.uuid4(),
                uploaded_by=USER_ID,
                filename="Q3_cohort.csv",
                display_name="Q3_cohort.csv",
                file_key="uploads/test/q3.csv",
                mime_type="text/csv",
                status=DocumentStatus.indexed,
            )
        )
        await db.commit()
    yield
    async with AsyncSessionLocal() as db:
        await db.execute(delete(AIQuery).where(AIQuery.user_id == USER_ID))
        await db.execute(delete(Document).where(Document.uploaded_by == USER_ID))
        await db.commit()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _our_queries():
    """Other users' rows may exist in the dev database — never assert on them."""
    return select(AIQuery).where(AIQuery.user_id == USER_ID)


def _parse_sse(body: str) -> list[dict]:
    return [
        json.loads(line[len("data: "):])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


@pytest.mark.asyncio
async def test_non_streaming_returns_answer_and_persists(client):
    response = await client.post(
        "/api/v1/agent/query", json={"question": "Mean glucose?", "stream": False}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["answer"] == ANSWER
    assert body["iterations"] == 2
    assert body["tokens_used"] == 300
    assert [call["tool"] for call in body["tool_calls"]] == ["get_document_list"]
    assert body["citations"][0]["document_name"] == "Q3_cohort.csv"

    async with AsyncSessionLocal() as db:
        saved = (await db.execute(_our_queries())).scalars().all()
    assert len(saved) == 1
    assert saved[0].answer == ANSWER
    assert saved[0].tool_calls[0]["tool"] == "get_document_list"
    assert saved[0].documents_accessed
    assert str(saved[0].conversation_id) == body["conversation_id"]


@pytest.mark.asyncio
async def test_streaming_emits_progress_then_done(client):
    response = await client.post(
        "/api/v1/agent/query", json={"question": "Mean glucose?", "stream": True}
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(response.text)
    types_in_order = [event["type"] for event in events]

    assert types_in_order[0] == "start"
    assert types_in_order[-1] == "done"
    assert "tool_call" in types_in_order
    assert "tool_result" in types_in_order
    assert types_in_order.index("answer_start") < types_in_order.index("answer_chunk")

    streamed_answer = "".join(e["content"] for e in events if e["type"] == "answer_chunk")
    assert streamed_answer == ANSWER

    done = events[-1]
    assert done["citations"][0]["document_name"] == "Q3_cohort.csv"
    assert done["tokens_used"] == 300

    async with AsyncSessionLocal() as db:
        saved = (await db.execute(_our_queries())).scalars().all()
    assert len(saved) == 1
    assert str(saved[0].id) == done["query_id"]


@pytest.mark.asyncio
async def test_conversation_history_is_replayed(client, fake_anthropic):
    first = await client.post(
        "/api/v1/agent/query", json={"question": "Mean glucose?", "stream": False}
    )
    conversation_id = first.json()["conversation_id"]

    fake_anthropic.calls.clear()
    await client.post(
        "/api/v1/agent/query",
        json={
            "question": "And in group B?",
            "stream": False,
            "conversation_id": conversation_id,
        },
    )

    replayed = fake_anthropic.calls[0]["messages"]
    assert replayed[0] == {"role": "user", "content": "Mean glucose?"}
    assert replayed[1] == {"role": "assistant", "content": ANSWER}
    assert replayed[2] == {"role": "user", "content": "And in group B?"}

    async with AsyncSessionLocal() as db:
        saved = (await db.execute(_our_queries())).scalars().all()
    assert {str(row.conversation_id) for row in saved} == {conversation_id}


@pytest.mark.asyncio
async def test_owned_project_is_accepted(client):
    project_id = uuid.uuid4()
    async with AsyncSessionLocal() as db:
        db.add(Project(id=project_id, name="Q3 Cohort", owner_id=USER_ID))
        await db.commit()

    response = await client.post(
        "/api/v1/agent/query",
        json={"question": "Mean glucose?", "stream": False, "project_id": str(project_id)},
    )
    assert response.status_code == 200

    async with AsyncSessionLocal() as db:
        saved = (await db.execute(_our_queries())).scalars().one()
        assert saved.project_id == project_id
        await db.execute(delete(Project).where(Project.id == project_id))
        await db.commit()


@pytest.mark.asyncio
async def test_unknown_project_is_rejected_before_the_agent_runs(client, fake_anthropic):
    """A project the caller doesn't own must 404 up front. Letting it through
    means paying Anthropic for an answer that then dies on the ai_queries
    foreign key.
    """
    for stream in (False, True):
        response = await client.post(
            "/api/v1/agent/query",
            json={
                "question": "Mean glucose?",
                "stream": stream,
                "project_id": str(uuid.uuid4()),
            },
        )
        # Streaming too: the check runs before the response starts, so this is
        # a real status code rather than an error event mid-stream.
        assert response.status_code == 404
        assert response.json()["code"] == "PROJECT_NOT_FOUND"
    assert fake_anthropic.calls == []

    async with AsyncSessionLocal() as db:
        assert (await db.execute(_our_queries())).scalars().all() == []


@pytest.mark.asyncio
async def test_stream_reports_errors_as_events_without_leaking_internals(client, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("INSERT INTO ai_queries ... [parameters: (UUID('secret'),)]")
        yield  # pragma: no cover — makes this an async generator

    monkeypatch.setattr(orchestrator_module.AgentOrchestrator, "stream", boom)

    response = await client.post(
        "/api/v1/agent/query", json={"question": "Mean glucose?", "stream": True}
    )
    events = _parse_sse(response.text)

    assert response.status_code == 200
    assert events[-1]["type"] == "error"
    # Internal exception text can carry SQL, table names and bound parameters.
    assert events[-1]["detail"] is None
    assert "ai_queries" not in response.text
