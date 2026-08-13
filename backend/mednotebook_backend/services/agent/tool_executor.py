"""Execution layer for the agent's tools.

Claude decides *which* tool to call; this module is what actually runs.
Every function returns a plain string — the exact text that goes back to
Claude as the `tool_result` content — and never raises: a tool failure is
information the model should see and route around, not a 500 for the user.

Scoping is enforced here, not by the model: `ToolExecutor` is constructed
with a user id and every query filters on it, so no prompt (or hallucinated
document UUID) can reach another user's data.
"""

import asyncio
import io
import logging
import uuid
from typing import Any, Optional

import anthropic
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models.chunk import DocumentChunk
from ...models.document import Document, DocumentStatus
from ...models.project import Project
from .. import storage as storage_service
from ..chunker import count_tokens
from ..search import hybrid_search

logger = logging.getLogger("mednotebook.agent.tools")

MAX_SEARCH_LIMIT = 20
DEFAULT_SEARCH_LIMIT = 8
MAX_CONTENT_TOKENS = 8000
LARGE_DOCUMENT_CHUNK_WARNING = 50
MAX_FILTER_ROWS_SHOWN = 50
COMPARE_CHUNKS_PER_DOCUMENT = 5
SUMMARY_SOURCE_CHUNKS = 10
SUMMARY_MODEL = "claude-sonnet-4-20250514"
SUMMARY_MAX_TOKENS = 1024

# mime type → the coarse `file_type` buckets exposed to the model
_FILE_TYPE_BY_MIME = {
    "application/pdf": "pdf",
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
    "application/vnd.ms-excel": "excel",
    "image/jpeg": "image",
    "image/png": "image",
    "image/tiff": "image",
    "text/plain": "text",
    "text/markdown": "text",
    "application/json": "text",
}

_TABULAR_MIME_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}


class ToolExecutor:
    """Runs agent tools against one user's data.

    Construct per conversation turn with the request's own AsyncSession —
    the same session the route is already using, so tool reads see anything
    that request has written.
    """

    def __init__(self, user_id: str, db: AsyncSession):
        self.user_id = str(user_id)
        self.db = db
        # Populated as tools run, and read afterwards by the orchestrator to
        # build structured citations and resolve IDs to names in progress
        # messages — the tool results themselves are prose for Claude, not a
        # machine-readable record.
        self.accessed_documents: dict[str, str] = {}
        self.citation_candidates: list[dict] = []

    def _record_passage(
        self, document_id: str, document_name: str, page_number: Optional[int], excerpt: str
    ) -> None:
        self.accessed_documents[str(document_id)] = document_name
        self.citation_candidates.append(
            {
                "document_id": str(document_id),
                "document_name": document_name,
                "page_number": page_number,
                "excerpt": excerpt,
            }
        )

    async def execute(self, tool_name: str, tool_input: dict) -> str:
        handlers = {
            "search_documents": self._search_documents,
            "get_document_content": self._get_document_content,
            "analyze_csv": self._analyze_csv,
            "compare_documents": self._compare_documents,
            "get_document_list": self._get_document_list,
            "summarize_document": self._summarize_document,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return f"Error: unknown tool '{tool_name}'. Available tools: {', '.join(sorted(handlers))}."

        try:
            return await handler(**(tool_input or {}))
        except TypeError as exc:
            # Wrong/missing arguments from the model — tell it precisely so it can retry.
            logger.warning("Bad arguments for tool %s: %s", tool_name, exc)
            return f"Error calling {tool_name}: invalid arguments ({exc})."
        except Exception as exc:
            logger.exception("Tool %s failed", tool_name)
            return f"Error running {tool_name}: {exc}"

    # ── Tool 1: search_documents ─────────────────────────────────────────────

    async def _search_documents(
        self,
        query: str,
        project_id: Optional[str] = None,
        document_ids: Optional[list[str]] = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> str:
        limit = max(1, min(int(limit or DEFAULT_SEARCH_LIMIT), MAX_SEARCH_LIMIT))

        results = await hybrid_search(
            self.db,
            query,
            self.user_id,
            project_id=project_id,
            document_ids=document_ids,
            limit=limit,
        )
        if not results:
            return (
                f"No relevant content found for '{query}'. Try different search terms "
                "or check if relevant documents have been uploaded."
            )

        lines = [f"Found {len(results)} relevant passages:", ""]
        for i, result in enumerate(results, start=1):
            self._record_passage(
                result.document_id, result.document_name, result.page_number, result.content
            )
            page = result.page_number if result.page_number is not None else "n/a"
            lines.append(f"[{i}] From: {result.document_name} (Page {page})")
            lines.append(f"Relevance: {round(result.similarity_score * 100)}%")
            lines.append(f"Content: {result.content}")
            lines.append(f"Document ID: {result.document_id}")
            lines.append("")
        return "\n".join(lines).rstrip()

    # ── Tool 2: get_document_content ─────────────────────────────────────────

    async def _get_document_content(
        self,
        document_id: str,
        pages: Optional[list[int]] = None,
        chunk_range: Optional[dict] = None,
    ) -> str:
        doc = await self._get_owned_document(document_id)
        if isinstance(doc, str):
            return doc

        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index)
        )
        if pages:
            stmt = stmt.where(DocumentChunk.page_number.in_([int(p) for p in pages]))
        elif chunk_range:
            start = int(chunk_range.get("start", 0))
            end = int(chunk_range.get("end", start))
            stmt = stmt.where(
                DocumentChunk.chunk_index >= start, DocumentChunk.chunk_index <= end
            )

        chunks = list((await self.db.execute(stmt)).scalars().all())
        if not chunks:
            if pages:
                return (
                    f"No content found in '{self._display_name(doc)}' for page(s) "
                    f"{', '.join(str(p) for p in pages)}. The document has "
                    f"{doc.page_count or 'an unknown number of'} page(s)."
                )
            return (
                f"Document '{self._display_name(doc)}' has no extracted text yet "
                f"(status: {doc.status.value})."
            )

        for chunk in chunks:
            self._record_passage(
                str(doc.id), self._display_name(doc), chunk.page_number, chunk.content
            )

        header = [
            f"Document: {self._display_name(doc)}",
            f"Type: {self._file_type(doc.mime_type)} | Pages: {doc.page_count or 'n/a'} | "
            f"Words: {doc.word_count or 'n/a'}",
        ]
        if pages is None and chunk_range is None and len(chunks) > LARGE_DOCUMENT_CHUNK_WARNING:
            header.append(
                f"Note: this is a large document ({len(chunks)} chunks). Content below may be "
                "truncated — request specific pages or a chunk_range for full fidelity."
            )
        header.extend(["", "Content:"])

        body_parts: list[str] = []
        current_page: Any = object()  # sentinel: never equals a real page number
        for chunk in chunks:
            if chunk.page_number != current_page:
                current_page = chunk.page_number
                label = f"Page {current_page}" if current_page is not None else "Page n/a"
                body_parts.append(f"\n--- {label} ---")
            body_parts.append(chunk.content)

        body, truncated = _truncate_to_tokens("\n".join(body_parts), MAX_CONTENT_TOKENS)
        output = "\n".join(header) + "\n" + body
        if truncated:
            output += (
                f"\n\n[Content truncated at {MAX_CONTENT_TOKENS} tokens. Request specific "
                "pages or a chunk_range to read the rest.]"
            )
        return output

    # ── Tool 3: analyze_csv ──────────────────────────────────────────────────

    async def _analyze_csv(
        self,
        document_id: str,
        operation: str,
        parameters: Optional[dict] = None,
    ) -> str:
        doc = await self._get_owned_document(document_id)
        if isinstance(doc, str):
            return doc

        if doc.mime_type not in _TABULAR_MIME_TYPES:
            return (
                f"'{self._display_name(doc)}' is a {self._file_type(doc.mime_type)} file, not a "
                "CSV or Excel spreadsheet. analyze_csv only works on tabular files — use "
                "search_documents or get_document_content instead."
            )
        if doc.file_key.startswith("pending/"):
            return f"'{self._display_name(doc)}' was never fully uploaded to storage — cannot analyze it."

        self.accessed_documents[str(doc.id)] = self._display_name(doc)

        # S3 download and pandas are both blocking and CPU-bound; keep them off the event loop.
        return await asyncio.to_thread(
            _analyze_tabular_file,
            doc.file_key,
            self._display_name(doc),
            doc.mime_type,
            operation,
            parameters or {},
        )

    # ── Tool 4: compare_documents ────────────────────────────────────────────

    async def _compare_documents(
        self, document_id_1: str, document_id_2: str, aspect: str
    ) -> str:
        doc_1 = await self._get_owned_document(document_id_1)
        if isinstance(doc_1, str):
            return doc_1
        doc_2 = await self._get_owned_document(document_id_2)
        if isinstance(doc_2, str):
            return doc_2

        results_1, results_2 = await asyncio.gather(
            hybrid_search(
                self.db, aspect, self.user_id,
                document_ids=[str(doc_1.id)], limit=COMPARE_CHUNKS_PER_DOCUMENT,
            ),
            hybrid_search(
                self.db, aspect, self.user_id,
                document_ids=[str(doc_2.id)], limit=COMPARE_CHUNKS_PER_DOCUMENT,
            ),
        )

        lines = [f"Comparison: {aspect}", ""]
        for doc, results in ((doc_1, results_1), (doc_2, results_2)):
            lines.append(f"FROM {self._display_name(doc)}:")
            if not results:
                lines.append(f"  (No passages about '{aspect}' found in this document.)")
            for result in results:
                self._record_passage(
                    result.document_id, result.document_name, result.page_number, result.content
                )
                page = result.page_number if result.page_number is not None else "n/a"
                lines.append(f"  (Page {page}) {result.content}")
            lines.append("")
        lines.append("Note: Direct comparison of the above passages.")
        return "\n".join(lines)

    # ── Tool 5: get_document_list ────────────────────────────────────────────

    async def _get_document_list(
        self, project_id: Optional[str] = None, file_type: str = "all"
    ) -> str:
        stmt = (
            select(Document, Project.name.label("project_name"))
            .outerjoin(Project, Document.project_id == Project.id)
            .where(Document.uploaded_by == uuid.UUID(self.user_id))
            .order_by(Document.created_at.desc())
        )
        if project_id:
            stmt = stmt.where(Document.project_id == uuid.UUID(project_id))

        rows = (await self.db.execute(stmt)).all()
        if file_type and file_type != "all":
            rows = [r for r in rows if self._file_type(r.Document.mime_type) == file_type]

        if not rows:
            scope = f" matching file type '{file_type}'" if file_type and file_type != "all" else ""
            return f"No documents found{scope}. The user has not uploaded any matching documents yet."

        grouped: dict[str, list[Document]] = {}
        for row in rows:
            grouped.setdefault(row.project_name or "", []).append(row.Document)
            self.accessed_documents.setdefault(str(row.Document.id), self._display_name(row.Document))

        lines = [f"Available documents ({len(rows)} total):", ""]
        # Real projects first (alphabetically), unfiled documents last.
        for project_name in sorted(grouped, key=lambda n: (n == "", n.lower())):
            lines.append(f"PROJECT: {project_name}" if project_name else "NO PROJECT:")
            for doc in grouped[project_name]:
                lines.append(f"- {self._display_name(doc)} ({self._describe(doc)})")
                lines.append(f"  ID: {doc.id}")
            lines.append("")
        lines.append("Note: Only 'indexed' documents can be searched.")
        return "\n".join(lines)

    # ── Tool 6: summarize_document ───────────────────────────────────────────

    async def _summarize_document(self, document_id: str, focus: Optional[str] = None) -> str:
        doc = await self._get_owned_document(document_id)
        if isinstance(doc, str):
            return doc

        self.accessed_documents[str(doc.id)] = self._display_name(doc)
        metadata = (
            f"Document: {self._display_name(doc)}\n"
            f"Type: {self._file_type(doc.mime_type)} | Pages: {doc.page_count or 'n/a'} | "
            f"Words: {doc.word_count or 'n/a'} | Status: {doc.status.value}"
        )

        if doc.summary and not focus:
            return f"{metadata}\n\nSummary:\n{doc.summary}"

        result = await self.db.execute(
            select(DocumentChunk.content, DocumentChunk.page_number)
            .where(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index)
            .limit(SUMMARY_SOURCE_CHUNKS)
        )
        rows = result.all()
        if not rows:
            return (
                f"{metadata}\n\nNo summary available — this document has no extracted text yet."
            )

        source_text = "\n\n".join(
            f"[Page {row.page_number if row.page_number is not None else 'n/a'}] {row.content}"
            for row in rows
        )
        summary = await asyncio.to_thread(
            _generate_summary, self._display_name(doc), source_text, focus
        )

        if not focus:
            # Cache only the general summary — a focused one isn't representative.
            doc.summary = summary
            await self.db.commit()

        focus_note = f" (focused on: {focus})" if focus else ""
        return f"{metadata}\n\nSummary{focus_note}:\n{summary}"

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _get_owned_document(self, document_id: str):
        """Return the Document, or an error string the model can act on."""
        try:
            doc_uuid = uuid.UUID(str(document_id))
        except (ValueError, AttributeError, TypeError):
            return (
                f"Error: '{document_id}' is not a valid document ID. Call get_document_list "
                "to get real document IDs — do not guess them."
            )

        result = await self.db.execute(
            select(Document).where(
                Document.id == doc_uuid,
                Document.uploaded_by == uuid.UUID(self.user_id),
            )
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            return (
                f"Error: no document with ID {document_id} is available to this user. "
                "Call get_document_list to see the available documents."
            )
        return doc

    @staticmethod
    def _display_name(doc: Document) -> str:
        return doc.display_name or doc.filename

    @staticmethod
    def _file_type(mime_type: Optional[str]) -> str:
        return _FILE_TYPE_BY_MIME.get(mime_type or "", "unknown")

    @classmethod
    def _describe(cls, doc: Document) -> str:
        parts = [cls._file_type(doc.mime_type).upper()]
        if doc.page_count:
            parts.append(f"{doc.page_count} pages")
        elif doc.word_count:
            parts.append(f"{doc.word_count:,} words")
        if doc.chunk_count:
            parts.append(f"{doc.chunk_count} chunks")
        parts.append(
            "indexed" if doc.status == DocumentStatus.indexed else f"not searchable ({doc.status.value})"
        )
        return ", ".join(parts)


# ── Summary generation ───────────────────────────────────────────────────────

def _generate_summary(document_name: str, source_text: str, focus: Optional[str]) -> str:
    """One-shot Claude call, separate from the agent loop — the summary comes
    back as a tool result, so it must not itself be a tool-using conversation.
    """
    if not settings.anthropic_api_key:
        return "Summary unavailable: ANTHROPIC_API_KEY is not configured on the server."

    focus_line = (
        f"Focus the summary specifically on: {focus}. If the excerpt does not cover that "
        "aspect, say so plainly."
        if focus
        else "Cover the document's purpose, methodology, and key findings."
    )
    prompt = (
        f"Summarize the following excerpt from the document '{document_name}'.\n"
        f"{focus_line}\n"
        "Use only what is in the excerpt — never add outside knowledge. Keep it under "
        "200 words and cite page numbers where the excerpt provides them.\n\n"
        f"{source_text}"
    )

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=SUMMARY_MODEL,
        max_tokens=SUMMARY_MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


# ── Tabular analysis ─────────────────────────────────────────────────────────

def _analyze_tabular_file(
    file_key: str,
    document_name: str,
    mime_type: Optional[str],
    operation: str,
    parameters: dict,
) -> str:
    """Download, load with pandas, run one operation. Runs in a worker thread.

    Nothing is written to disk: the file is loaded from an in-memory buffer,
    so there is no temp file to leak or clean up.
    """
    try:
        file_content = storage_service.download_file(file_key)
    except Exception as exc:
        return f"Error: could not retrieve '{document_name}' from storage ({exc})."

    try:
        if mime_type == "text/csv":
            df = pd.read_csv(io.BytesIO(file_content))
        else:
            df = pd.read_excel(io.BytesIO(file_content))
    except Exception as exc:
        return f"Error: could not parse '{document_name}' as a table ({exc})."

    if df.empty:
        return f"'{document_name}' contains no data rows."

    operations = {
        "summary": _op_summary,
        "describe_columns": _op_describe_columns,
        "filter_rows": _op_filter_rows,
        "calculate_stats": _op_calculate_stats,
        "find_trends": _op_find_trends,
        "compare_groups": _op_compare_groups,
        "find_outliers": _op_find_outliers,
        "correlation": _op_correlation,
    }
    handler = operations.get(operation)
    if handler is None:
        return f"Error: unsupported operation '{operation}'. Supported: {', '.join(operations)}."

    try:
        body = handler(df, parameters)
    except _AnalysisError as exc:
        return f"Analysis of '{document_name}' failed: {exc}"
    except Exception as exc:
        logger.exception("analyze_csv operation %s failed", operation)
        return f"Analysis of '{document_name}' failed: {exc}"

    header = (
        f"Analysis of {document_name} — operation: {operation}\n"
        f"Rows analyzed: {len(df):,} | Columns: {len(df.columns)}"
    )
    quality = _data_quality_notes(df)
    return f"{header}\n\n{body}\n\n{quality}"


class _AnalysisError(Exception):
    """A problem with the request itself (bad column, bad operator) — reported
    back to Claude verbatim so it can correct the call.
    """


def _op_summary(df: pd.DataFrame, params: dict) -> str:
    dtypes = "\n".join(f"| {col} | {dtype} | {int(df[col].notna().sum()):,} |"
                       for col, dtype in df.dtypes.items())
    out = [
        "**Structure**",
        "",
        "| Column | Type | Non-null |",
        "|---|---|---|",
        dtypes,
    ]
    numeric = df.select_dtypes("number")
    if not numeric.empty:
        out += ["", "**Numeric summary**", "", _df_to_markdown(numeric.describe().round(4).reset_index())]
    return "\n".join(out)


def _op_describe_columns(df: pd.DataFrame, params: dict) -> str:
    rows = []
    for col in df.columns:
        series = df[col]
        rows.append(
            f"| {col} | {series.dtype} | {int(series.isna().sum()):,} | "
            f"{int(series.nunique(dropna=True)):,} | {_example_value(series)} |"
        )
    return "\n".join(
        ["| Column | Type | Nulls | Unique | Example |", "|---|---|---|---|---|", *rows]
    )


def _op_filter_rows(df: pd.DataFrame, params: dict) -> str:
    column = _require_column(df, params.get("column"))
    operator = str(params.get("operator", "==")).strip()
    value = params.get("value")

    series = df[column]
    comparisons = {
        "==": lambda: series == value,
        "eq": lambda: series == value,
        "!=": lambda: series != value,
        "ne": lambda: series != value,
        ">": lambda: pd.to_numeric(series, errors="coerce") > float(value),
        "gt": lambda: pd.to_numeric(series, errors="coerce") > float(value),
        ">=": lambda: pd.to_numeric(series, errors="coerce") >= float(value),
        "gte": lambda: pd.to_numeric(series, errors="coerce") >= float(value),
        "<": lambda: pd.to_numeric(series, errors="coerce") < float(value),
        "lt": lambda: pd.to_numeric(series, errors="coerce") < float(value),
        "<=": lambda: pd.to_numeric(series, errors="coerce") <= float(value),
        "lte": lambda: pd.to_numeric(series, errors="coerce") <= float(value),
        "contains": lambda: series.astype(str).str.contains(str(value), case=False, na=False),
        "in": lambda: series.isin(value if isinstance(value, list) else [value]),
        "isnull": lambda: series.isna(),
        "notnull": lambda: series.notna(),
    }
    if operator not in comparisons:
        raise _AnalysisError(
            f"unsupported operator '{operator}'. Supported: {', '.join(comparisons)}"
        )

    matched = df[comparisons[operator]().fillna(False)]
    if matched.empty:
        return f"No rows match `{column} {operator} {value!r}`."

    shown = matched.head(MAX_FILTER_ROWS_SHOWN)
    out = [f"{len(matched):,} of {len(df):,} rows match `{column} {operator} {value!r}`.", ""]
    out.append(_df_to_markdown(shown))
    if len(matched) > MAX_FILTER_ROWS_SHOWN:
        out.append(f"\n(Showing the first {MAX_FILTER_ROWS_SHOWN} matching rows.)")
    return "\n".join(out)


def _op_calculate_stats(df: pd.DataFrame, params: dict) -> str:
    columns = _numeric_columns(df, params.get("columns"))
    metrics = params.get("metrics") or ["mean", "median", "std", "min", "max", "p25", "p75"]

    computations = {
        "count": lambda s: s.count(),
        "sum": lambda s: s.sum(),
        "mean": lambda s: s.mean(),
        "median": lambda s: s.median(),
        "std": lambda s: s.std(),
        "min": lambda s: s.min(),
        "max": lambda s: s.max(),
        "p25": lambda s: s.quantile(0.25),
        "p50": lambda s: s.quantile(0.50),
        "p75": lambda s: s.quantile(0.75),
        "p95": lambda s: s.quantile(0.95),
    }
    unknown = [m for m in metrics if m not in computations]
    if unknown:
        raise _AnalysisError(
            f"unsupported metric(s) {', '.join(unknown)}. Supported: {', '.join(computations)}"
        )

    header = "| Column | " + " | ".join(metrics) + " |"
    divider = "|---" * (len(metrics) + 1) + "|"
    rows = []
    for col in columns:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        values = " | ".join(_fmt_number(computations[m](series)) for m in metrics)
        rows.append(f"| {col} | {values} |")
    return "\n".join([header, divider, *rows])


def _op_find_trends(df: pd.DataFrame, params: dict) -> str:
    date_column = params.get("date_column") or _detect_date_column(df)
    numeric_columns = _numeric_columns(df, params.get("columns"))

    if date_column is None:
        out = ["No date/time column detected — showing value distributions instead.", ""]
        for col in numeric_columns[:5]:
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            if series.empty:
                continue
            counts = pd.cut(series, bins=min(10, max(2, series.nunique()))).value_counts().sort_index()
            out.append(f"**{col}** (n={len(series):,}, mean={_fmt_number(series.mean())})")
            out.append("")
            out.append("| Range | Count |")
            out.append("|---|---|")
            out += [f"| {interval} | {int(count):,} |" for interval, count in counts.items()]
            out.append("")
        return "\n".join(out).rstrip()

    dated = df.copy()
    dated[date_column] = pd.to_datetime(dated[date_column], errors="coerce")
    dated = dated.dropna(subset=[date_column]).sort_values(date_column)
    if dated.empty:
        raise _AnalysisError(f"column '{date_column}' could not be parsed as dates")

    out = [f"Trend over `{date_column}` ({dated[date_column].min().date()} → "
           f"{dated[date_column].max().date()}):", ""]
    for col in numeric_columns[:5]:
        series = pd.to_numeric(dated[col], errors="coerce")
        by_period = series.groupby(dated[date_column].dt.to_period("M")).mean().dropna()
        if by_period.empty:
            continue
        direction = _trend_direction(by_period)
        out.append(f"**{col}** — {direction}")
        out.append("")
        out.append("| Period | Mean |")
        out.append("|---|---|")
        out += [f"| {period} | {_fmt_number(value)} |" for period, value in by_period.items()]
        out.append("")
    return "\n".join(out).rstrip()


def _op_compare_groups(df: pd.DataFrame, params: dict) -> str:
    group_column = _require_column(df, params.get("group_column"))
    value_columns = _numeric_columns(df, params.get("value_columns"))

    numeric = df[value_columns].apply(pd.to_numeric, errors="coerce")
    grouped = numeric.groupby(df[group_column]).agg(["count", "mean", "std", "min", "max"])

    out = [f"Grouped by `{group_column}` ({df[group_column].nunique(dropna=True):,} groups):", ""]
    for col in value_columns:
        out.append(f"**{col}**")
        out.append("")
        out.append("| Group | Count | Mean | Std | Min | Max |")
        out.append("|---|---|---|---|---|---|")
        for group, row in grouped[col].iterrows():
            out.append(
                f"| {group} | {int(row['count']):,} | {_fmt_number(row['mean'])} | "
                f"{_fmt_number(row['std'])} | {_fmt_number(row['min'])} | {_fmt_number(row['max'])} |"
            )
        out.append("")
    return "\n".join(out).rstrip()


def _op_find_outliers(df: pd.DataFrame, params: dict) -> str:
    columns = _numeric_columns(df, params.get("columns"))
    multiplier = float(params.get("iqr_multiplier", 1.5))

    out = [f"Outliers by IQR method (outside {multiplier}× IQR):", ""]
    any_found = False
    for col in columns:
        series = pd.to_numeric(df[col], errors="coerce")
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if pd.isna(iqr) or iqr == 0:
            out.append(f"**{col}** — no spread in the data (IQR = 0); outlier detection not meaningful.")
            out.append("")
            continue
        lower, upper = q1 - multiplier * iqr, q3 + multiplier * iqr
        mask = (series < lower) | (series > upper)
        count = int(mask.sum())
        out.append(
            f"**{col}** — {count:,} outlier(s); expected range "
            f"{_fmt_number(lower)} to {_fmt_number(upper)}"
        )
        if count:
            any_found = True
            out.append("")
            out.append(_df_to_markdown(df[mask].head(MAX_FILTER_ROWS_SHOWN)))
            if count > MAX_FILTER_ROWS_SHOWN:
                out.append(f"\n(Showing the first {MAX_FILTER_ROWS_SHOWN} outlier rows.)")
        out.append("")
    if not any_found:
        out.append("No outliers found in the analyzed columns.")
    return "\n".join(out).rstrip()


def _op_correlation(df: pd.DataFrame, params: dict) -> str:
    columns = _numeric_columns(df, params.get("columns"))
    if len(columns) < 2:
        raise _AnalysisError("correlation needs at least two numeric columns")

    numeric = df[columns].apply(pd.to_numeric, errors="coerce")
    matrix = numeric.corr(method="pearson").round(3)

    out = ["Pearson correlation matrix:", "", _df_to_markdown(matrix.reset_index())]

    strong = []
    for i, col_a in enumerate(columns):
        for col_b in columns[i + 1:]:
            value = matrix.loc[col_a, col_b]
            if pd.notna(value) and abs(value) >= 0.7:
                strong.append(f"- {col_a} ↔ {col_b}: {value:+.3f}")
    if strong:
        out += ["", "Strong correlations (|r| ≥ 0.7):", *strong]
    return "\n".join(out)


# ── Analysis helpers ─────────────────────────────────────────────────────────

def _require_column(df: pd.DataFrame, column: Optional[str]) -> str:
    if not column:
        raise _AnalysisError(f"a column must be specified. Available columns: {', '.join(map(str, df.columns))}")
    if column not in df.columns:
        raise _AnalysisError(
            f"column '{column}' not found. Available columns: {', '.join(map(str, df.columns))}"
        )
    return column


def _numeric_columns(df: pd.DataFrame, requested: Optional[list]) -> list:
    if requested:
        missing = [c for c in requested if c not in df.columns]
        if missing:
            raise _AnalysisError(
                f"column(s) {', '.join(map(str, missing))} not found. "
                f"Available columns: {', '.join(map(str, df.columns))}"
            )
        return list(requested)

    columns = list(df.select_dtypes("number").columns)
    if not columns:
        raise _AnalysisError(
            f"no numeric columns in this file. Available columns: {', '.join(map(str, df.columns))}"
        )
    return columns


def _detect_date_column(df: pd.DataFrame) -> Optional[str]:
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            return col
    for col in df.columns:
        if not any(hint in str(col).lower() for hint in ("date", "time", "day", "visit", "when")):
            continue
        parsed = pd.to_datetime(df[col], errors="coerce")
        if parsed.notna().mean() > 0.8:
            return col
    return None


def _trend_direction(series: pd.Series) -> str:
    if len(series) < 2:
        return "not enough periods to establish a direction"
    delta = series.iloc[-1] - series.iloc[0]
    if series.iloc[0] == 0 or pd.isna(series.iloc[0]):
        return "increasing" if delta > 0 else "decreasing" if delta < 0 else "flat"
    pct = delta / abs(series.iloc[0]) * 100
    if abs(pct) < 1:
        return "essentially flat across the period"
    return f"{'increasing' if delta > 0 else 'decreasing'} {abs(pct):.1f}% from first to last period"


def _data_quality_notes(df: pd.DataFrame) -> str:
    notes = []

    null_counts = df.isna().sum()
    nulled = null_counts[null_counts > 0]
    if not nulled.empty:
        details = ", ".join(
            f"{col} ({int(count):,}, {count / len(df):.0%})" for col, count in nulled.items()
        )
        notes.append(f"- Missing values: {details}")

    duplicates = int(df.duplicated().sum())
    if duplicates:
        notes.append(f"- {duplicates:,} fully duplicated row(s)")

    mixed = [
        str(col) for col in df.select_dtypes("object").columns
        if pd.to_numeric(df[col], errors="coerce").notna().mean() > 0.5
    ]
    if mixed:
        notes.append(
            f"- Column(s) stored as text but mostly numeric: {', '.join(mixed)} "
            "— values may be inconsistently formatted"
        )

    constant = [str(col) for col in df.columns if df[col].nunique(dropna=True) <= 1]
    if constant:
        notes.append(f"- Column(s) with a single value throughout: {', '.join(constant)}")

    if not notes:
        return "Data quality: no missing values, duplicates, or formatting inconsistencies detected."
    return "Data quality notes:\n" + "\n".join(notes)


def _df_to_markdown(df: pd.DataFrame) -> str:
    columns = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(_fmt_cell(v) for v in row) + " |")
    return "\n".join(lines)


def _fmt_cell(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return _fmt_number(value)
    return str(value).replace("|", "\\|")


def _fmt_number(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    if isinstance(value, (int,)) or (isinstance(value, float) and float(value).is_integer()):
        return f"{int(value):,}"
    try:
        return f"{float(value):,.4g}"
    except (TypeError, ValueError):
        return str(value)


def _example_value(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return ""
    return _fmt_cell(non_null.iloc[0])[:60]


def _truncate_to_tokens(text: str, max_tokens: int) -> tuple[str, bool]:
    if count_tokens(text) <= max_tokens:
        return text, False
    # Binary search on characters — cheaper than re-encoding a huge document
    # repeatedly, and exact token precision doesn't matter for a cutoff.
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if count_tokens(text[:mid]) <= max_tokens:
            low = mid
        else:
            high = mid - 1
    return text[:low].rsplit(" ", 1)[0], True
