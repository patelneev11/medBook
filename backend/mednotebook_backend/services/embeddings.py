import logging
import time
import unicodedata
from functools import lru_cache
from typing import Optional

import numpy as np
import tiktoken
from sentence_transformers import SentenceTransformer

from ..config import settings
from .embeddings_exceptions import EmbeddingException

logger = logging.getLogger("mednotebook.embeddings")

# cl100k_base is a reasonable generic token-count proxy for truncation
# purposes — MiniLM has its own WordPiece tokenizer and silently truncates
# at 256 tokens internally, but we truncate first so long inputs don't
# waste time getting cleaned/batched only to be chopped by the model anyway.
_ENCODING = tiktoken.get_encoding("cl100k_base")
_MAX_TOKENS = 8000
_BATCH_SIZE = 100
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = (2, 4, 8)


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    # Loaded once per process and cached — construction reads model weights
    # from disk/HF cache, which takes noticeably longer than any single embed.
    return SentenceTransformer(settings.embedding_model)


def _clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = unicodedata.normalize("NFKC", text)
    return text.strip()


def _truncate_to_max_tokens(text: str, max_tokens: int = _MAX_TOKENS) -> str:
    tokens = _ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated = _ENCODING.decode(tokens[:max_tokens])
    # Cut back to the last full word rather than an arbitrary token boundary.
    return truncated.rsplit(" ", 1)[0]


def _encode(texts: list[str]) -> list[list[float]]:
    vectors = _get_model().encode(
        texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
    )
    return vectors.tolist()


def generate_embedding(text: str, chunk_id: Optional[str] = None) -> list[float]:
    cleaned = _truncate_to_max_tokens(_clean_text(text))
    token_count = len(_ENCODING.encode(cleaned))

    last_exc: Optional[Exception] = None
    for attempt in range(_MAX_RETRIES):
        try:
            vector = _encode([cleaned])[0]
            logger.info("Embedded chunk (%d tokens, local model, $0 cost)", token_count)
            return vector
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                backoff = _RETRY_BACKOFF_SECONDS[attempt]
                logger.warning(
                    "Embedding attempt %d/%d failed: %s — retrying in %ds",
                    attempt + 1, _MAX_RETRIES, exc, backoff,
                )
                time.sleep(backoff)

    raise EmbeddingException(
        message=f"Failed to generate embedding after {_MAX_RETRIES} attempts: {last_exc}",
        chunk_id=chunk_id,
        retry_count=_MAX_RETRIES,
    )


def generate_embeddings_batch(
    texts: list[str], chunk_ids: Optional[list[str]] = None
) -> list[list[float]]:
    if not texts:
        return []
    chunk_ids = chunk_ids or [None] * len(texts)
    cleaned = [_truncate_to_max_tokens(_clean_text(t)) for t in texts]

    results: list[Optional[list[float]]] = [None] * len(cleaned)
    total_batches = (len(cleaned) + _BATCH_SIZE - 1) // _BATCH_SIZE

    for batch_num, start in enumerate(range(0, len(cleaned), _BATCH_SIZE), start=1):
        batch = cleaned[start:start + _BATCH_SIZE]
        logger.info("Embedding batch %d/%d (%d chunks)...", batch_num, total_batches, len(batch))
        try:
            vectors = _encode(batch)
            for i, vector in enumerate(vectors):
                results[start + i] = vector
        except Exception as exc:
            # The batch call failed as a whole — fall back to embedding this
            # batch one at a time so a single bad chunk doesn't blank out
            # every chunk that would otherwise have embedded fine.
            logger.warning(
                "Batch %d/%d failed as a whole (%s) — retrying its chunks individually",
                batch_num, total_batches, exc,
            )
            for i, text in enumerate(batch):
                idx = start + i
                try:
                    results[idx] = generate_embedding(text, chunk_id=chunk_ids[idx])
                except EmbeddingException as chunk_exc:
                    logger.error(
                        "Chunk %s failed to embed after retries, using zero vector placeholder: %s",
                        chunk_ids[idx], chunk_exc,
                    )
                    results[idx] = [0.0] * settings.embedding_dimensions

    return results


def estimate_embedding_cost(texts: list[str]) -> dict:
    total_tokens = sum(len(_ENCODING.encode(t)) for t in texts)
    return {
        "total_tokens": total_tokens,
        # Local model — no per-call API cost, unlike a hosted embeddings API.
        "estimated_cost_usd": 0.0,
        "chunk_count": len(texts),
    }


def test_embedding_quality(query: str, chunks: list[str]) -> list[dict]:
    """Development/debug helper — not used in the processing pipeline.

    Embeds a query and a set of candidate chunks, and returns the chunks
    ranked by cosine similarity to the query, for manually sanity-checking
    that the embedding model is actually separating relevant from
    irrelevant text.
    """
    query_vector = np.array(generate_embedding(query))
    chunk_vectors = generate_embeddings_batch(chunks)

    results = [
        # Both vectors are unit-normalized (normalize_embeddings=True), so
        # a plain dot product is already the cosine similarity.
        {"chunk": chunk, "similarity": float(np.dot(query_vector, vector))}
        for chunk, vector in zip(chunks, chunk_vectors)
    ]
    return sorted(results, key=lambda r: r["similarity"], reverse=True)