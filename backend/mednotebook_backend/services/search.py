import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chunk import DocumentChunk
from ..models.document import Document
from .embeddings import generate_embedding

_RRF_K = 60  # standard Reciprocal Rank Fusion constant


@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    document_name: str
    project_id: Optional[str]
    mime_type: Optional[str]
    chunk_index: int
    content: str
    context_before: Optional[str]
    context_after: Optional[str]
    page_number: Optional[int]
    similarity_score: float
    chunk_type: Optional[str]


def _row_to_result(row) -> SearchResult:
    return SearchResult(
        chunk_id=str(row.id),
        document_id=str(row.document_id),
        document_name=row.document_name,
        project_id=str(row.project_id) if row.project_id else None,
        mime_type=row.mime_type,
        chunk_index=row.chunk_index,
        content=row.content,
        context_before=None,
        context_after=None,
        page_number=row.page_number,
        similarity_score=float(row.similarity_score),
        chunk_type=row.chunk_type.value if row.chunk_type else None,
    )


def _apply_common_filters(stmt, *, since: Optional[datetime], mime_types: Optional[list[str]]):
    if since is not None:
        stmt = stmt.where(Document.created_at >= since)
    if mime_types:
        stmt = stmt.where(Document.mime_type.in_(mime_types))
    return stmt


async def semantic_search(
    db: AsyncSession,
    query: str,
    user_id: str,
    project_id: Optional[str] = None,
    document_ids: Optional[list[str]] = None,
    limit: int = 10,
    similarity_threshold: float = 0.35,
    since: Optional[datetime] = None,
    mime_types: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Vector similarity search over the caller's own chunks.

    Note: this takes `db` as an explicit first argument (not in the
    original signature) — every query here needs a session, and this
    codebase passes AsyncSession down from the FastAPI route rather than
    having services open their own (that pattern is reserved for the
    Celery task, which has no request-scoped session to borrow).
    """
    query_vector = generate_embedding(query)

    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    similarity = (1 - distance).label("similarity_score")

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            DocumentChunk.page_number,
            DocumentChunk.chunk_type,
            func.coalesce(Document.display_name, Document.filename).label("document_name"),
            Document.project_id,
            Document.mime_type,
            similarity,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            Document.uploaded_by == uuid.UUID(user_id),
            DocumentChunk.embedding.is_not(None),
            similarity > similarity_threshold,
        )
        .order_by(distance)
        .limit(limit)
    )
    if project_id is not None:
        stmt = stmt.where(Document.project_id == uuid.UUID(project_id))
    if document_ids:
        stmt = stmt.where(DocumentChunk.document_id.in_([uuid.UUID(d) for d in document_ids]))
    stmt = _apply_common_filters(stmt, since=since, mime_types=mime_types)

    rows = (await db.execute(stmt)).all()
    results = [_row_to_result(row) for row in rows]

    results = _dedupe_by_content(results)
    results = await _attach_context(db, results)
    return _group_by_document(results)


async def keyword_search(
    db: AsyncSession,
    query: str,
    user_id: str,
    project_id: Optional[str] = None,
    document_ids: Optional[list[str]] = None,
    limit: int = 10,
    since: Optional[datetime] = None,
    mime_types: Optional[list[str]] = None,
) -> list[SearchResult]:
    """PostgreSQL full-text search fallback for when semantic_search finds
    nothing (e.g. a query built entirely from terms/acronyms the embedding
    model doesn't represent well) — call this yourself when that happens,
    it isn't chained automatically inside semantic_search.

    document_ids/project_id aren't in the original spec for this function,
    but were added anyway: without them, hybrid_search would leak keyword
    hits from documents a caller explicitly scoped out of the semantic side,
    which defeats the point of scoping search to begin with.
    """
    # websearch_to_tsquery (vs. plainto_tsquery/to_tsquery) tolerates
    # arbitrary user input — quotes, stray punctuation — without raising a
    # syntax error, which matters since this receives raw question text.
    tsquery = func.websearch_to_tsquery("english", query)
    rank = func.ts_rank_cd(DocumentChunk.content_tsv, tsquery).label("similarity_score")

    stmt = (
        select(
            DocumentChunk.id,
            DocumentChunk.document_id,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            DocumentChunk.page_number,
            DocumentChunk.chunk_type,
            func.coalesce(Document.display_name, Document.filename).label("document_name"),
            Document.project_id,
            Document.mime_type,
            rank,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            Document.uploaded_by == uuid.UUID(user_id),
            DocumentChunk.content_tsv.op("@@")(tsquery),
        )
        .order_by(rank.desc())
        .limit(limit)
    )
    if project_id is not None:
        stmt = stmt.where(Document.project_id == uuid.UUID(project_id))
    if document_ids:
        stmt = stmt.where(DocumentChunk.document_id.in_([uuid.UUID(d) for d in document_ids]))
    stmt = _apply_common_filters(stmt, since=since, mime_types=mime_types)

    rows = (await db.execute(stmt)).all()
    results = [_row_to_result(row) for row in rows]

    results = _dedupe_by_content(results)
    results = await _attach_context(db, results)
    return _group_by_document(results)


async def hybrid_search(
    db: AsyncSession,
    query: str,
    user_id: str,
    project_id: Optional[str] = None,
    document_ids: Optional[list[str]] = None,
    limit: int = 10,
    since: Optional[datetime] = None,
    mime_types: Optional[list[str]] = None,
) -> list[SearchResult]:
    """Fuse semantic + keyword search via Reciprocal Rank Fusion.

    RRF combines *rank position* from each list, not raw scores — cosine
    similarity (0-1) and ts_rank_cd (unbounded, corpus-dependent) aren't on
    comparable scales, so blending them directly would be meaningless.
    """
    # Pull a wider candidate pool than the final limit so there's enough
    # overlap between the two lists for fusion to actually do something.
    # A low but nonzero semantic threshold: 0.0 was tried first and let
    # every chunk in a small library into the pool regardless of relevance
    # — with few enough documents, "least dissimilar of what exists" always
    # produces something, so a nonsense query still surfaced two results.
    # This still admits weak matches (below the standalone 0.35 default)
    # since fusion needs some breadth, but no longer admits everything.
    pool_size = max(limit * 3, 20)

    semantic_results = await semantic_search(
        db, query, user_id, project_id=project_id, document_ids=document_ids,
        limit=pool_size, similarity_threshold=0.2, since=since, mime_types=mime_types,
    )
    keyword_results = await keyword_search(
        db, query, user_id, project_id=project_id, document_ids=document_ids, limit=pool_size,
        since=since, mime_types=mime_types,
    )

    scores: dict[str, float] = {}
    by_id: dict[str, SearchResult] = {}
    for rank, result in enumerate(semantic_results, start=1):
        scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + 1 / (_RRF_K + rank)
        by_id[result.chunk_id] = result
    for rank, result in enumerate(keyword_results, start=1):
        scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + 1 / (_RRF_K + rank)
        by_id.setdefault(result.chunk_id, result)

    ranked_ids = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)[:limit]
    # Raw RRF scores live around 1/_RRF_K (~0.016 for a rank-1 hit in one
    # list, ~0.033 for rank-1 in both) — nowhere near the 0-1 range semantic/
    # keyword scores use. The frontend renders similarity_score * 100 as a
    # relevance bar for every mode, so an unnormalized RRF score would show
    # hybrid's *best* matches as ~2-4% bars. Normalize against the max a
    # chunk can achieve (rank 1 in both lists) so the scale is comparable
    # while leaving the fused ranking itself untouched (monotonic transform).
    max_possible_rrf = 2 / (_RRF_K + 1)
    fused = []
    for chunk_id in ranked_ids:
        result = by_id[chunk_id]
        result.similarity_score = min(scores[chunk_id] / max_possible_rrf, 1.0)
        fused.append(result)

    return _group_by_document(fused)


async def _attach_context(db: AsyncSession, results: list[SearchResult]) -> list[SearchResult]:
    """Fetch chunk_index-1 and chunk_index+1 for every result in one batched
    query, so the caller gets a bit of surrounding context without a full
    re-retrieval — one query total, not one per result.
    """
    if not results:
        return results

    needed: set[tuple[uuid.UUID, int]] = set()
    for r in results:
        doc_id = uuid.UUID(r.document_id)
        if r.chunk_index > 0:
            needed.add((doc_id, r.chunk_index - 1))
        needed.add((doc_id, r.chunk_index + 1))

    stmt = select(DocumentChunk.document_id, DocumentChunk.chunk_index, DocumentChunk.content).where(
        tuple_(DocumentChunk.document_id, DocumentChunk.chunk_index).in_(needed)
    )
    rows = (await db.execute(stmt)).all()
    neighbors = {(row.document_id, row.chunk_index): row.content for row in rows}

    for r in results:
        doc_id = uuid.UUID(r.document_id)
        r.context_before = neighbors.get((doc_id, r.chunk_index - 1)) if r.chunk_index > 0 else None
        r.context_after = neighbors.get((doc_id, r.chunk_index + 1))

    return results


def _dedupe_by_content(results: list[SearchResult]) -> list[SearchResult]:
    """Chunk overlap means the same text can legitimately surface as two
    different chunks — keep only the highest-scoring copy of each.
    """
    best: dict[str, SearchResult] = {}
    for r in results:
        current_best = best.get(r.content)
        if current_best is None or r.similarity_score > current_best.similarity_score:
            best[r.content] = r
    # Preserve the original score-ranked order among the survivors.
    return [r for r in results if best[r.content] is r]


def _group_by_document(results: list[SearchResult]) -> list[SearchResult]:
    """Group same-document chunks together (documents ordered by their best
    match), chunks within a document ordered by chunk_index — coherent
    reading order for whatever consumes these next, instead of chunks from
    the same document scattered out of sequence by raw score.
    """
    if not results:
        return results

    order: list[str] = []
    groups: dict[str, list[SearchResult]] = {}
    best_score: dict[str, float] = {}
    for r in results:
        if r.document_id not in groups:
            groups[r.document_id] = []
            order.append(r.document_id)
            best_score[r.document_id] = r.similarity_score
        groups[r.document_id].append(r)
        best_score[r.document_id] = max(best_score[r.document_id], r.similarity_score)

    order.sort(key=lambda doc_id: best_score[doc_id], reverse=True)

    grouped: list[SearchResult] = []
    for doc_id in order:
        grouped.extend(sorted(groups[doc_id], key=lambda r: r.chunk_index))
    return grouped


async def find_similar_documents(
    db: AsyncSession,
    document_id: str,
    user_id: str,
    limit: int = 5,
    sample_chunks: int = 3,
) -> list[dict]:
    """"Similar documents" for a document card — not a text query. Uses the
    source document's own first `sample_chunks` chunk embeddings (already
    computed at index time, not re-embedded here) as the query vectors,
    finds the nearest chunks elsewhere in the user's library, and
    aggregates to document level by each candidate's single best-matching
    chunk across the sample.
    """
    doc_uuid = uuid.UUID(document_id)
    user_uuid = uuid.UUID(user_id)

    result = await db.execute(
        select(DocumentChunk.embedding)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            DocumentChunk.document_id == doc_uuid,
            Document.uploaded_by == user_uuid,
            DocumentChunk.embedding.is_not(None),
        )
        .order_by(DocumentChunk.chunk_index)
        .limit(sample_chunks)
    )
    source_vectors = [row[0] for row in result.all()]
    if not source_vectors:
        # Source document isn't indexed yet (or doesn't belong to this
        # user) — nothing to compare against.
        return []

    best_per_document: dict[str, dict] = {}
    for vector in source_vectors:
        distance = DocumentChunk.embedding.cosine_distance(vector)
        similarity = (1 - distance).label("similarity_score")
        stmt = (
            select(
                DocumentChunk.document_id,
                func.coalesce(Document.display_name, Document.filename).label("document_name"),
                Document.mime_type,
                similarity,
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                Document.uploaded_by == user_uuid,
                DocumentChunk.document_id != doc_uuid,
                DocumentChunk.embedding.is_not(None),
            )
            .order_by(distance)
            .limit(limit * 3)  # wider pool per sample chunk, narrowed after aggregation
        )
        for row in (await db.execute(stmt)).all():
            candidate_id = str(row.document_id)
            score = float(row.similarity_score)
            current = best_per_document.get(candidate_id)
            if current is None or score > current["similarity_score"]:
                best_per_document[candidate_id] = {
                    "document_id": candidate_id,
                    "document_name": row.document_name,
                    "mime_type": row.mime_type,
                    "similarity_score": score,
                }

    ranked = sorted(best_per_document.values(), key=lambda d: d["similarity_score"], reverse=True)
    return ranked[:limit]