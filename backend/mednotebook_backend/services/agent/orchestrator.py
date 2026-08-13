"""The agent loop.

Claude drives: it decides which tools to call and in what order, we execute
them and hand the results back, and the loop repeats until it stops asking
for tools. Everything the UI shows as "thinking" comes from the `on_step`
callback fired inside this loop.

The loop is bounded by `max_iterations` — a runaway model that keeps calling
tools has to terminate somewhere, and terminating with a partial answer is
better than an unbounded bill.
"""

import asyncio
import inspect
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, Union

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from .system_prompt import build_workspace_stats, get_system_prompt
from .tool_executor import ToolExecutor
from .tools import TOOLS

logger = logging.getLogger("mednotebook.agent.orchestrator")

AGENT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MAX_ITERATIONS = 10
# Enough excerpt to show the user why a citation was made, not the whole chunk.
CITATION_EXCERPT_CHARS = 400
RESULT_SUMMARY_CHARS = 160

OnStep = Callable[[dict], Union[None, Awaitable[None]]]

# "[Doc name, Page 4]" / "[Doc name, p. 4]" / "[Doc name]" — the citation
# format the system prompt mandates. Commas inside a document name are
# tolerated: only a trailing "page N" segment is treated as the page.
_CITATION_RE = re.compile(
    r"\[([^\[\]]+?)(?:\s*,\s*(?:page|pg\.?|p\.?)\s*(\d+))?\]", re.IGNORECASE
)


@dataclass
class Citation:
    document_id: str
    document_name: str
    page_number: Optional[int]
    excerpt: str


@dataclass
class ToolCallRecord:
    tool_name: str
    input_summary: str
    result_summary: str
    execution_time_ms: int


@dataclass
class AgentResponse:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    total_iterations: int = 0
    documents_accessed: list[str] = field(default_factory=list)
    tokens_used: int = 0
    response_time_ms: int = 0
    # True when the loop hit max_iterations before Claude finished — the
    # answer is real but may be incomplete, and the UI says so.
    truncated: bool = False


class AgentOrchestrator:
    def __init__(
        self,
        user_id: str,
        db: AsyncSession,
        model: str = AGENT_MODEL,
        max_iterations: int = MAX_ITERATIONS,
    ):
        self.user_id = str(user_id)
        self.db = db
        self.model = model
        self.max_iterations = max_iterations
        self.tool_executor = ToolExecutor(self.user_id, db)
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(
        self,
        question: str,
        conversation_history: Optional[list[dict]] = None,
        project_id: Optional[str] = None,
        on_step: Optional[OnStep] = None,
    ) -> AgentResponse:
        started = time.perf_counter()

        messages: list[dict] = list(conversation_history or [])
        messages.append({"role": "user", "content": question})

        system_prompt = await self._build_system_prompt(project_id)

        tool_calls: list[ToolCallRecord] = []
        tokens_used = 0
        iterations = 0
        answer = ""
        truncated = False

        while True:
            iterations += 1
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )
            tokens_used += _count_tokens(response)

            text_this_turn = _text_from(response)

            if response.stop_reason != "tool_use":
                answer = text_this_turn
                break

            # Text alongside a tool_use block is Claude narrating its plan,
            # not the answer — surface it as thinking, keep it out of the
            # final answer so citations aren't diluted by "let me check...".
            if text_this_turn:
                answer = text_this_turn  # fallback if the loop ends early
                await _emit(
                    on_step,
                    {"type": "thinking", "text": text_this_turn, "step": iterations},
                )

            tool_uses = [block for block in response.content if block.type == "tool_use"]

            if iterations >= self.max_iterations:
                # Stop before executing another round of tools: the next
                # Claude call would just ask for more.
                truncated = True
                await _emit(
                    on_step,
                    {
                        "type": "max_iterations",
                        "step": iterations,
                        "message": (
                            "This question needed more research steps than allowed in a single "
                            "turn — answering with what has been gathered so far."
                        ),
                    },
                )
                break

            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in tool_uses:
                tool_input = dict(block.input or {})
                input_summary = summarize_input(
                    block.name, tool_input, self.tool_executor.accessed_documents
                )
                await _emit(
                    on_step,
                    {
                        "type": "tool_call",
                        "tool": block.name,
                        "input_summary": input_summary,
                        "step": iterations,
                    },
                )

                tool_started = time.perf_counter()
                result = await self.tool_executor.execute(block.name, tool_input)
                elapsed_ms = int((time.perf_counter() - tool_started) * 1000)

                result_summary = _summarize_result(result)
                tool_calls.append(
                    ToolCallRecord(
                        tool_name=block.name,
                        input_summary=input_summary,
                        result_summary=result_summary,
                        execution_time_ms=elapsed_ms,
                    )
                )
                await _emit(
                    on_step,
                    {
                        "type": "tool_result",
                        "tool": block.name,
                        "result_summary": result_summary,
                        "execution_time_ms": elapsed_ms,
                        "step": iterations,
                    },
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        answer = answer.strip()
        if truncated and answer:
            answer += (
                "\n\n_Note: this question required more research steps than a single turn "
                "allows, so the answer above may be incomplete. Ask a narrower follow-up "
                "to go deeper._"
            )
        elif truncated:
            answer = (
                "I wasn't able to finish researching this question within one turn. "
                "Try narrowing it — for example, ask about one document or one metric at a time."
            )

        return AgentResponse(
            answer=answer,
            citations=self._build_citations(answer),
            tool_calls=tool_calls,
            total_iterations=iterations,
            documents_accessed=list(self.tool_executor.accessed_documents),
            tokens_used=tokens_used,
            response_time_ms=int((time.perf_counter() - started) * 1000),
            truncated=truncated,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _build_system_prompt(self, project_id: Optional[str]) -> str:
        stats = await build_workspace_stats(self.db, self.user_id)
        prompt = get_system_prompt(None, stats)
        if project_id:
            prompt += (
                f"\n\nThe user is currently working inside project {project_id}. Prefer that "
                "project when searching, and pass it as project_id to search_documents unless "
                "the user explicitly asks about their whole workspace."
            )
        return prompt

    def _build_citations(self, answer: str) -> list[Citation]:
        """Turn the `[Document, Page N]` markers in the answer into structured
        citations, resolved against the passages the tools actually returned.

        Only markers matching a real retrieved document become citations —
        a name Claude invented has nothing to resolve against and is dropped,
        so the citation list can never point at something that wasn't read.
        """
        candidates = self.tool_executor.citation_candidates
        if not candidates or not answer:
            return []

        by_name: dict[str, list[dict]] = {}
        for candidate in candidates:
            by_name.setdefault(candidate["document_name"].casefold(), []).append(candidate)

        citations: list[Citation] = []
        seen: set[tuple[str, Optional[int]]] = set()
        for raw_name, raw_page in _CITATION_RE.findall(answer):
            name = raw_name.strip()
            page = int(raw_page) if raw_page else None

            matches = by_name.get(name.casefold())
            if matches is None:
                # Tolerate the model trimming or extending the name slightly
                # ("Diabetes Cohort" for "Diabetes Cohort Q3.pdf").
                matches = next(
                    (
                        group
                        for known, group in by_name.items()
                        if known.startswith(name.casefold()) or name.casefold().startswith(known)
                    ),
                    None,
                )
            if not matches:
                continue

            best = next((c for c in matches if c["page_number"] == page), matches[0])
            key = (best["document_id"], page)
            if key in seen:
                continue
            seen.add(key)

            citations.append(
                Citation(
                    document_id=best["document_id"],
                    document_name=best["document_name"],
                    page_number=page if page is not None else best["page_number"],
                    excerpt=best["excerpt"][:CITATION_EXCERPT_CHARS],
                )
            )
        return citations


def summarize_input(
    tool_name: str, tool_input: dict, document_names: Optional[dict[str, str]] = None
) -> str:
    """Human-readable one-liner for a tool call — this is the "thinking" text
    the user sees while the agent works.
    """
    names = document_names or {}

    def name_of(key: str) -> str:
        doc_id = str(tool_input.get(key, "") or "")
        return names.get(doc_id) or "document"

    if tool_name == "search_documents":
        return f"Searching for '{tool_input.get('query', '')}'"
    if tool_name == "get_document_content":
        pages = tool_input.get("pages")
        suffix = f" (page{'s' if len(pages) > 1 else ''} {', '.join(map(str, pages))})" if pages else ""
        return f"Reading {name_of('document_id')}{suffix}"
    if tool_name == "analyze_csv":
        operation = str(tool_input.get("operation", "")).replace("_", " ")
        suffix = f" — {operation}" if operation else ""
        return f"Analyzing data in {name_of('document_id')}{suffix}"
    if tool_name == "compare_documents":
        aspect = tool_input.get("aspect")
        suffix = f" on {aspect}" if aspect else ""
        return f"Comparing {name_of('document_id_1')} and {name_of('document_id_2')}{suffix}"
    if tool_name == "get_document_list":
        return "Getting document list"
    if tool_name == "summarize_document":
        focus = tool_input.get("focus")
        suffix = f" ({focus})" if focus else ""
        return f"Summarizing {name_of('document_id')}{suffix}"
    return f"Running {tool_name}"


def _summarize_result(result: str) -> str:
    first_line = next((line for line in result.splitlines() if line.strip()), "")
    if len(first_line) > RESULT_SUMMARY_CHARS:
        return first_line[:RESULT_SUMMARY_CHARS].rstrip() + "…"
    return first_line


def _text_from(response: Any) -> str:
    return "\n".join(
        block.text.strip() for block in response.content if block.type == "text" and block.text.strip()
    )


def _count_tokens(response: Any) -> int:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0
    return int(getattr(usage, "input_tokens", 0) or 0) + int(getattr(usage, "output_tokens", 0) or 0)


async def _emit(on_step: Optional[OnStep], event: dict) -> None:
    """Fire the progress callback, tolerating sync or async callables.

    A broken callback must never take down the agent run — the user would
    lose a real answer over a UI progress message.
    """
    if on_step is None:
        return
    try:
        result = on_step(event)
        if inspect.isawaitable(result):
            await result
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("on_step callback failed for event %s", event.get("type"))
